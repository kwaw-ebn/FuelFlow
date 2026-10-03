"""Revocable sessions, encrypted owner TOTP and persistent login limits."""
import os, secrets, hashlib, base64
from datetime import timedelta, timezone
import jwt, pyotp
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy import select, String, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.exc import IntegrityError
from .main import Base, DB, Actor, User, secret, hash_password, verify_password, permit, audit, get
from .operations import now
router=APIRouter()
class AuthSession(Base):
    __tablename__='auth_sessions'
    id:Mapped[str]=mapped_column(String(64),primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    expires:Mapped[object]=mapped_column(DateTime(timezone=True))
    last_seen:Mapped[object]=mapped_column(DateTime(timezone=True),default=now)
    revoked:Mapped[bool]=mapped_column(default=False)
class RateBucket(Base):
    __tablename__='auth_rate_buckets'
    key:Mapped[str]=mapped_column(String(64),primary_key=True)
    count:Mapped[int]=mapped_column(default=0)
    expires:Mapped[object]=mapped_column(DateTime(timezone=True))
class RecoveryCode(Base):
    __tablename__='mfa_recovery_codes'
    id:Mapped[int]=mapped_column(primary_key=True)
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),index=True)
    digest:Mapped[str]=mapped_column(String(64),unique=True)
    used:Mapped[bool]=mapped_column(default=False)
class MFAReplay(Base):
    __tablename__='mfa_steps'
    user_id:Mapped[int]=mapped_column(ForeignKey('users.id'),primary_key=True)
    step:Mapped[int]=mapped_column(default=-1)
def aware(dt):return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt
def owner_mfa_required():return os.getenv('REQUIRE_OWNER_MFA','true' if os.getenv('APP_ENV')=='production' else 'false').lower()=='true'
def cipher():
    key=os.getenv('MFA_ENCRYPTION_SECRET') or secret()
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(key.encode()).digest()))
def consume_limit(db,key,limit):
    digest=hashlib.sha256(f'{key}:{int(now().timestamp())//60}'.encode()).hexdigest();table=RateBucket.__table__
    if db.bind.dialect.name=='postgresql':from sqlalchemy.dialects.postgresql import insert
    else:from sqlalchemy.dialects.sqlite import insert
    stmt=insert(table).values(key=digest,count=1,expires=now()+timedelta(minutes=2))
    stmt=stmt.on_conflict_do_update(index_elements=['key'],set_={'count':table.c.count+1}).returning(table.c.count)
    count=db.scalar(stmt);db.commit()
    if count>limit:raise HTTPException(429,'Too many attempts. Try again in one minute.',headers={'Retry-After':'60'})
    if secrets.randbelow(100)==0:db.query(RateBucket).filter(RateBucket.expires<now()).delete(synchronize_session=False);db.commit()
def throttle(db,request,email=''):
    consume_limit(db,'ip:'+(request.client.host if request.client else 'unknown'),30);consume_limit(db,'account:'+email.lower(),6)
def validate_session(db,user,payload,request):
    session=db.get(AuthSession,payload.get('jti',''))
    if not session or session.user_id!=user.id or session.revoked or aware(session.expires)<=now() or aware(session.last_seen)<now()-timedelta(minutes=15) or payload.get('ver')!=user.session_version:raise HTTPException(401,'Session expired. Sign in again.')
    if (payload.get('scope')=='mfa_setup' or (user.role=='owner' and owner_mfa_required() and not user.mfa_enabled)) and request.url.path not in ['/auth/me','/auth/logout','/auth/mfa/setup','/auth/mfa/confirm']:raise HTTPException(403,'Enroll owner two-factor authentication before using the system')
    session.last_seen=now();db.commit();request.state.session_id=session.id
def issue_session(db,user,scope='full'):
    id=secrets.token_hex(24);expiry=now()+timedelta(minutes=30);db.add(AuthSession(id=id,user_id=user.id,expires=expiry));db.commit()
    token=jwt.encode({'sub':str(user.id),'jti':id,'ver':user.session_version,'scope':scope,'iss':'fuelflow','aud':'fuelflow','exp':expiry},secret(),algorithm='HS256')
    return {'access_token':token,'token_type':'bearer','mfa_enrollment_required':scope=='mfa_setup'}
def valid_factor(db,user,code):
    if not code:return False
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    recovery=db.scalar(select(RecoveryCode).where(RecoveryCode.user_id==user.id,RecoveryCode.digest==hashlib.sha256(code.encode()).hexdigest(),RecoveryCode.used==False))
    if recovery:recovery.used=True;db.flush();return True
    if not user.mfa_secret:return False
    totp=pyotp.TOTP(cipher().decrypt(user.mfa_secret.encode()).decode());step=int(now().timestamp())//30
    matched=next((i for i in [step-1,step,step+1] if secrets.compare_digest(totp.at(i*30),code)),None);state=db.get(MFAReplay,user.id)
    if matched is None or (state and matched<=state.step):return False
    if not state:db.add(MFAReplay(user_id=user.id,step=matched))
    else:state.step=matched
    db.flush();return True
class LoginInput(BaseModel):
    email:EmailStr
    password:str=Field(min_length=1,max_length=128)
    otp:str | None=Field(default=None,max_length=64)
@router.post('/auth/login')
def login(body:LoginInput,db:DB,request:Request):
    throttle(db,request,str(body.email));user=db.scalar(select(User).where(User.email==str(body.email).lower()))
    if not user or not user.active or not verify_password(body.password,user.password):raise HTTPException(401,'Invalid credentials')
    if user.mfa_enabled and not valid_factor(db,user,body.otp):raise HTTPException(401,'Enter a valid authentication or recovery code')
    return issue_session(db,user,'mfa_setup' if user.role=='owner' and owner_mfa_required() and not user.mfa_enabled else 'full')
@router.post('/auth/logout')
def logout(request:Request,db:DB,actor:Actor):
    db.get(AuthSession,request.state.session_id).revoked=True;db.commit();return {'status':'signed_out'}
class PasswordInput(BaseModel):
    current_password:str=Field(max_length=128)
    new_password:str=Field(min_length=12,max_length=128)
@router.post('/auth/password')
def change_password(body:PasswordInput,db:DB,actor:Actor):
    if not verify_password(body.current_password,actor.password):raise HTTPException(401,'Current password is incorrect')
    actor.password=hash_password(body.new_password);actor.session_version+=1;audit(db,actor,'password.change','All previous sessions revoked');db.commit();return {'status':'changed; sign in again'}
class MFASetupInput(BaseModel):
    password:str=Field(max_length=128)
@router.post('/auth/mfa/setup')
def mfa_setup(body:MFASetupInput,db:DB,actor:Actor):
    consume_limit(db,'factor:'+str(actor.id),6)
    if actor.mfa_enabled:raise HTTPException(409,'Two-factor authentication is already enabled')
    if not verify_password(body.password,actor.password):raise HTTPException(401,'Password incorrect')
    value=pyotp.random_base32();actor.mfa_secret=cipher().encrypt(value.encode()).decode();db.commit()
    return {'secret':value,'uri':pyotp.TOTP(value).provisioning_uri(name=actor.email,issuer_name='FuelFlow Ghana')}
class MFAConfirmInput(BaseModel):
    otp:str=Field(min_length=6,max_length=64)
@router.post('/auth/mfa/confirm')
def mfa_confirm(body:MFAConfirmInput,db:DB,actor:Actor):
    consume_limit(db,'factor:'+str(actor.id),6)
    if actor.mfa_enabled or not actor.mfa_secret:raise HTTPException(409,'Start two-factor enrollment first')
    if not valid_factor(db,actor,body.otp):raise HTTPException(422,'Authentication code invalid')
    actor.mfa_enabled=True;actor.session_version+=1;codes=[secrets.token_hex(8) for _ in range(8)]
    for code in codes:db.add(RecoveryCode(user_id=actor.id,digest=hashlib.sha256(code.encode()).hexdigest()))
    audit(db,actor,'mfa.enable','Authenticator enabled; recovery codes issued');db.commit();return {**issue_session(db,actor),'recovery_codes':codes}
class StaffControlInput(BaseModel):
    active:bool
    reason:str=Field(min_length=5,max_length=500)
@router.post('/staff/{id}/access')
def staff_access(id:int,body:StaffControlInput,db:DB,actor:Actor):
    permit(actor,'owner');u=get(db,User,id)
    if u.id==actor.id or u.role=='owner':raise HTTPException(422,'Owner access cannot be disabled here')
    old=u.active;u.active=body.active;u.session_version+=1;audit(db,actor,'staff.access',f'user={id}; before={old}; after={u.active}; reason={body.reason}');db.commit();return {'status':'updated'}
class StaffResetInput(BaseModel):
    password:str=Field(min_length=12,max_length=128)
    reason:str=Field(min_length=5,max_length=500)
@router.post('/staff/{id}/password')
def staff_password(id:int,body:StaffResetInput,db:DB,actor:Actor):
    permit(actor,'owner');u=get(db,User,id)
    if u.role=='owner':raise HTTPException(422,'Use the secure owner recovery CLI')
    u.password=hash_password(body.password);u.session_version+=1;audit(db,actor,'staff.password_reset',f'user={id}; reason={body.reason}');db.commit();return {'status':'reset; sessions revoked'}
class BootstrapInput(BaseModel):
    token:str=Field(min_length=32,max_length=256)
    email:EmailStr
    name:str=Field(min_length=1,max_length=120)
    password:str=Field(min_length=12,max_length=128)
@router.get('/setup/status')
def setup_status(db:DB):return {'requires_setup':not bool(db.scalar(select(User.id).where(User.role=='owner')))}
@router.post('/setup/owner')
def setup_owner(body:BootstrapInput,db:DB,request:Request):
    throttle(db,request,'bootstrap');expected=os.getenv('BOOTSTRAP_TOKEN','')
    if len(expected)<32 or not secrets.compare_digest(body.token,expected):raise HTTPException(403,'Invalid installation access code')
    if db.bind.dialect.name=='postgresql':db.execute(select(func.pg_advisory_xact_lock(88441001)))
    if db.scalar(select(User.id).where(User.role=='owner')):raise HTTPException(409,'Installation is already configured')
    user=User(email=str(body.email).lower(),name=body.name,password=hash_password(body.password),role='owner');db.add(user);db.flush();audit(db,user,'owner.bootstrap','First owner created');db.commit();return {'status':'Owner created. Sign in to enroll two-factor authentication.'}
@router.get('/ready')
def readiness(db:DB):db.execute(select(User.id).limit(1));return {'status':'ready'}
def install(app):
    @app.exception_handler(IntegrityError)
    async def integrity_error(request,exc):return JSONResponse(status_code=409,content={'detail':'This record conflicts with an existing entry or database constraint'})
    @app.middleware('http')
    async def headers(request,call_next):
        response=await call_next(request);response.headers['X-Content-Type-Options']='nosniff';response.headers['X-Frame-Options']='DENY';response.headers['Referrer-Policy']='no-referrer';response.headers['Cache-Control']='no-store'
        if os.getenv('APP_ENV')=='production':response.headers['Strict-Transport-Security']='max-age=31536000; includeSubDomains'
        return response
