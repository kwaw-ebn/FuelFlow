import os, secrets, hashlib, hmac
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated
import jwt
from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, String, Numeric, ForeignKey, DateTime, Boolean, UniqueConstraint, CheckConstraint, Index, Date, JSON, Text, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session

DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///./fuelflow.db').replace('postgres://', 'postgresql+psycopg://').replace('postgresql://', 'postgresql+psycopg://')
engine = create_engine(DATABASE_URL, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False}} if DATABASE_URL.startswith('sqlite') else {}))
SessionLocal = sessionmaker(engine, expire_on_commit=False)
class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    password: Mapped[str] = mapped_column(String(256))
    role: Mapped[str] = mapped_column(String(30))
    station_id: Mapped[int | None] = mapped_column(ForeignKey('stations.id'))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    session_version: Mapped[int] = mapped_column(default=0, server_default='0')
    mfa_secret: Mapped[str | None] = mapped_column(Text)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text('false'))
class Station(Base):
    __tablename__ = 'stations'
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str] = mapped_column(String(30), unique=True)
    region: Mapped[str] = mapped_column(String(60))
    district: Mapped[str] = mapped_column(String(120))
class Product(Base):
    __tablename__ = 'fuel_products'
    __table_args__ = (CheckConstraint('price > 0', name='ck_product_price'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), index=True)
    name: Mapped[str] = mapped_column(String(60))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
class Tank(Base):
    __tablename__ = 'tanks'
    __table_args__ = (CheckConstraint('capacity > 0 AND stock >= 0 AND stock <= capacity AND reorder >= 0 AND reorder <= capacity', name='ck_tank_volume'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey('fuel_products.id'))
    name: Mapped[str] = mapped_column(String(60))
    capacity: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    stock: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    reorder: Mapped[Decimal] = mapped_column(Numeric(14, 3))
class Nozzle(Base):
    __tablename__ = 'nozzles'
    __table_args__ = (CheckConstraint('meter >= 0', name='ck_nozzle_meter'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), index=True)
    tank_id: Mapped[int] = mapped_column(ForeignKey('tanks.id'))
    name: Mapped[str] = mapped_column(String(60))
    meter: Mapped[Decimal] = mapped_column(Numeric(16, 3))
class Shift(Base):
    __tablename__ = 'shifts'
    __table_args__ = (
        CheckConstraint('closing IS NULL OR closing >= opening', name='ck_shift_meter'),
        CheckConstraint('cash >= 0 AND momo >= 0 AND card >= 0 AND credit >= 0 AND litres >= 0 AND price > 0', name='ck_shift_amounts'),
        Index('uq_active_nozzle_shift', 'nozzle_id', unique=True, postgresql_where=text("status IN ('open','submitted')"), sqlite_where=text("status IN ('open','submitted')")),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), index=True)
    nozzle_id: Mapped[int] = mapped_column(ForeignKey('nozzles.id'))
    attendant_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    opening: Mapped[Decimal] = mapped_column(Numeric(16, 3))
    closing: Mapped[Decimal | None] = mapped_column(Numeric(16, 3))
    price: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    litres: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    expected: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cash: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    momo: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    card: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default='0')
    business_date: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date(), index=True)
    variance: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    status: Mapped[str] = mapped_column(String(20), default='open')
    started: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class Delivery(Base):
    __tablename__ = 'fuel_deliveries'
    __table_args__ = (UniqueConstraint('station_id', 'reference'), CheckConstraint('received_litres > 0 AND waybill_litres > 0 AND cost_per_litre > 0', name='ck_delivery_amounts'))
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), index=True)
    tank_id: Mapped[int] = mapped_column(ForeignKey('tanks.id'))
    reference: Mapped[str] = mapped_column(String(100))
    supplier: Mapped[str] = mapped_column(String(120))
    waybill_litres: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    received_litres: Mapped[Decimal] = mapped_column(Numeric(14, 3))
    cost_per_litre: Mapped[Decimal] = mapped_column(Numeric(14, 4))
    business_date: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date(), index=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class Expense(Base):
    __tablename__ = 'expenses'
    __table_args__ = (CheckConstraint('amount > 0', name='ck_expense_amount'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey('stations.id'), index=True)
    description: Mapped[str] = mapped_column(String(300))
    business_date: Mapped[date] = mapped_column(Date, default=lambda: datetime.now(timezone.utc).date(), index=True)
    status: Mapped[str] = mapped_column(String(20), default='pending', server_default='pending')
    recorded_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    approved_by: Mapped[int | None] = mapped_column(ForeignKey('users.id'))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class Audit(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    details: Mapped[str] = mapped_column(String(1000))
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

def db():
    with SessionLocal() as session: yield session
DB = Annotated[Session, Depends(db)]
bearer = HTTPBearer()
def secret():
    value = os.getenv('JWT_SECRET', '')
    if len(value) < 32: raise HTTPException(503, 'Set JWT_SECRET to at least 32 random characters')
    return value

def hash_password(password):
    salt = secrets.token_hex(16)
    return salt + ':' + hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex()
def verify_password(password, hashed):
    salt, value = hashed.split(':')
    return hmac.compare_digest(value, hashlib.scrypt(password.encode(), salt=salt.encode(), n=16384, r=8, p=1).hex())
def current(request: Request, db: DB, auth: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]):
    try:
        payload = jwt.decode(auth.credentials, secret(), algorithms=['HS256'], issuer='fuelflow', audience='fuelflow')
        user = db.get(User, int(payload['sub']))
    except (jwt.PyJWTError, ValueError, KeyError): raise HTTPException(401, 'Invalid or expired session')
    if not user or not user.active: raise HTTPException(401, 'Account unavailable')
    from .security import validate_session
    validate_session(db, user, payload, request)
    return user
Actor = Annotated[User, Depends(current)]
def permit(user, *roles):
    if user.role not in roles: raise HTTPException(403, 'This action is not allowed for your role')
def scoped(user, station_id):
    if user.role != 'owner' and user.station_id != station_id: raise HTTPException(403, 'Station access denied')
def get(db, model, id):
    obj = db.get(model, id)
    if not obj: raise HTTPException(404, 'Record not found')
    return obj
def audit(db, actor, action, details): db.add(Audit(user_id=actor.id, action=action, details=details))
def save(db, actor, obj, action):
    db.add(obj); db.flush(); audit(db, actor, action, f'{obj.__tablename__}:{obj.id}'); db.commit(); return obj

app = FastAPI(title='FuelFlow Ghana', version='0.2.0', docs_url=None if os.getenv('APP_ENV')=='production' else '/docs', redoc_url=None)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(','), allow_credentials=False, allow_methods=['GET','POST'], allow_headers=['Authorization','Content-Type'])
@app.get('/health')
def health(): return {'status': 'ok'}
@app.get('/auth/me')
def me(actor: Actor): return {'id':actor.id,'name':actor.name,'email':actor.email,'role':actor.role,'station_id':actor.station_id,'mfa_enabled':actor.mfa_enabled}
class StationInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str = Field(min_length=1, max_length=30)
    region: str = Field(min_length=1, max_length=60)
    district: str = Field(min_length=1, max_length=120)
@app.post('/stations')
def station_create(body: StationInput, db: DB, actor: Actor):
    permit(actor, 'owner')
    if db.scalar(select(Station).where(Station.code==body.code)): raise HTTPException(409,'Station code already exists')
    return save(db, actor, Station(**body.model_dump()), 'station.create')
@app.get('/stations')
def station_list(db: DB, actor: Actor):
    stmt=select(Station)
    if actor.role!='owner': stmt=stmt.where(Station.id==actor.station_id)
    return db.scalars(stmt).all()
class StaffInput(BaseModel):
    email: str = Field(min_length=5, max_length=254, pattern=r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
    name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)
    role: str = Field(pattern='^(manager|supervisor|attendant|accountant|auditor)$')
    station_id: int
@app.post('/staff')
def staff_create(body: StaffInput, db: DB, actor: Actor):
    permit(actor,'owner'); get(db,Station,body.station_id)
    if db.scalar(select(User).where(User.email==body.email.lower())): raise HTTPException(409,'Email already registered')
    data=body.model_dump(); data['email']=body.email.lower(); data['password']=hash_password(body.password)
    return {'id':save(db,actor,User(**data),'staff.create').id}
@app.get('/staff')
def staff_list(station_id: int, db: DB, actor: Actor):
    permit(actor,'owner','manager','supervisor'); scoped(actor,station_id)
    return [{'id':u.id,'name':u.name,'role':u.role,'email':u.email,'active':u.active} for u in db.scalars(select(User).where(User.station_id==station_id)).all()]
class ProductInput(BaseModel):
    station_id: int
    name: str = Field(min_length=1,max_length=60)
    price: Decimal = Field(gt=0,max_digits=14,decimal_places=4)
@app.post('/products')
def product_create(body: ProductInput, db: DB, actor: Actor):
    permit(actor,'owner'); scoped(actor,body.station_id); get(db,Station,body.station_id)
    from .operations import FuelPrice
    product=Product(**body.model_dump());db.add(product);db.flush()
    db.add(FuelPrice(product_id=product.id,previous_price=body.price,price=body.price,reason='Initial price',changed_by=actor.id))
    return save(db,actor,product,'product.create')
class TankInput(BaseModel):
    station_id: int
    product_id: int
    name: str = Field(min_length=1,max_length=60)
    capacity: Decimal = Field(gt=0,max_digits=14,decimal_places=3)
    stock: Decimal = Field(ge=0,max_digits=14,decimal_places=3)
    reorder: Decimal = Field(ge=0,max_digits=14,decimal_places=3)
@app.post('/tanks')
def tank_create(body: TankInput, db: DB, actor: Actor):
    permit(actor,'owner'); scoped(actor,body.station_id)
    product=get(db,Product,body.product_id)
    if product.station_id!=body.station_id or body.stock>body.capacity or body.reorder>body.capacity: raise HTTPException(422,'Invalid tank product or capacity')
    from .operations import writable_day, movement
    writable_day(db, actor, body.station_id, date.today())
    tank=Tank(**body.model_dump()); db.add(tank); db.flush()
    movement(db,tank,body.stock,date.today(),'opening',str(tank.id),actor.id)
    return save(db,actor,tank,'tank.create')
class NozzleInput(BaseModel):
    tank_id: int
    name: str = Field(min_length=1,max_length=60)
    meter: Decimal = Field(ge=0,max_digits=16,decimal_places=3)
@app.post('/nozzles')
def nozzle_create(body: NozzleInput, db: DB, actor: Actor):
    permit(actor,'owner'); tank=get(db,Tank,body.tank_id); scoped(actor,tank.station_id)
    return save(db,actor,Nozzle(station_id=tank.station_id,**body.model_dump()),'nozzle.create')
@app.get('/inventory')
def inventory(station_id: int, db: DB, actor: Actor):
    scoped(actor,station_id)
    if actor.role=='attendant':
        assigned=db.scalars(select(Shift).where(Shift.station_id==station_id,Shift.attendant_id==actor.id)).all()
        nozzle_ids={s.nozzle_id for s in assigned}
        return {'products':[], 'tanks':[], 'nozzles':db.scalars(select(Nozzle).where(Nozzle.id.in_(nozzle_ids))).all()}
    return {'products':db.scalars(select(Product).where(Product.station_id==station_id)).all(),'tanks':db.scalars(select(Tank).where(Tank.station_id==station_id)).all(),'nozzles':db.scalars(select(Nozzle).where(Nozzle.station_id==station_id)).all()}
class OpenShift(BaseModel):
    business_date: date = Field(default_factory=lambda: datetime.now(timezone.utc).date())
    nozzle_id: int
    attendant_id: int
@app.post('/shifts')
def open_shift(body: OpenShift, db: DB, actor: Actor):
    permit(actor,'owner','manager','supervisor')
    from .operations import writable_day
    n=get(db,Nozzle,body.nozzle_id)
    writable_day(db,actor,n.station_id,body.business_date)
    nozzle=db.scalar(select(Nozzle).where(Nozzle.id==body.nozzle_id).with_for_update().execution_options(populate_existing=True))
    if not nozzle: raise HTTPException(404,'Nozzle not found')
    scoped(actor,nozzle.station_id); staff=get(db,User,body.attendant_id)
    if not staff.active or staff.role!='attendant' or staff.station_id!=nozzle.station_id: raise HTTPException(422,'Choose an active attendant at this station')
    if db.scalar(select(Shift).where(Shift.nozzle_id==nozzle.id,Shift.status.in_(['open','submitted']))): raise HTTPException(409,'Nozzle already has an active shift')
    from .operations import Equipment
    equipment=db.scalar(select(Equipment).where(Equipment.nozzle_id==nozzle.id))
    if equipment and equipment.status!='operational': raise HTTPException(409,'Nozzle equipment is under maintenance')
    tank=get(db,Tank,nozzle.tank_id); product=get(db,Product,tank.product_id)
    return save(db,actor,Shift(business_date=body.business_date,station_id=nozzle.station_id,nozzle_id=nozzle.id,attendant_id=staff.id,opening=nozzle.meter,price=product.price),'shift.open')
@app.get('/shifts')
def shifts(station_id: int, db: DB, actor: Actor):
    scoped(actor,station_id); stmt=select(Shift).where(Shift.station_id==station_id)
    if actor.role=='attendant': stmt=stmt.where(Shift.attendant_id==actor.id)
    return db.scalars(stmt.order_by(Shift.id.desc())).all()
class SubmitShift(BaseModel):
    closing: Decimal = Field(ge=0,max_digits=16,decimal_places=3)
    cash: Decimal = Field(ge=0,max_digits=14,decimal_places=2)
    momo: Decimal = Field(ge=0,max_digits=14,decimal_places=2)
    card: Decimal = Field(ge=0,max_digits=14,decimal_places=2)
@app.post('/shifts/{id}/submit')
def submit_shift(id: int, body: SubmitShift, db: DB, actor: Actor):
    permit(actor,'owner','manager','supervisor','attendant')
    from .operations import writable_day
    existing=get(db,Shift,id)
    writable_day(db,actor,existing.station_id,existing.business_date)
    shift=db.scalar(select(Shift).where(Shift.id==id).with_for_update().execution_options(populate_existing=True))
    if not shift: raise HTTPException(404,'Shift not found')
    scoped(actor,shift.station_id)
    if actor.role=='attendant' and actor.id!=shift.attendant_id: raise HTTPException(403,'Assigned attendant only')
    if shift.status!='open': raise HTTPException(409,'Shift already submitted or locked')
    if body.closing<shift.opening: raise HTTPException(422,'Closing meter cannot be below opening meter')
    for key,value in body.model_dump().items(): setattr(shift,key,value)
    shift.litres=body.closing-shift.opening; shift.expected=(shift.litres*shift.price).quantize(Decimal('0.01'))
    from .operations import shift_credit
    shift.credit, credit_litres=shift_credit(db,shift.id)
    if credit_litres>shift.litres or shift.credit>shift.expected: raise HTTPException(422,'Meter sales are below the credit sales recorded for this shift')
    shift.variance=body.cash+body.momo+body.card+shift.credit-shift.expected; shift.status='submitted'
    return save(db,actor,shift,'shift.submit')
@app.post('/shifts/{id}/reconcile')
def reconcile(id: int, db: DB, actor: Actor):
    permit(actor,'owner','manager','supervisor')
    from .operations import writable_day
    existing=get(db,Shift,id)
    writable_day(db,actor,existing.station_id,existing.business_date)
    shift=db.scalar(select(Shift).where(Shift.id==id).with_for_update().execution_options(populate_existing=True))
    if not shift: raise HTTPException(404,'Shift not found')
    scoped(actor,shift.station_id)
    if shift.status!='submitted': raise HTTPException(409,'Only submitted shifts can be reconciled')
    nozzle=db.scalar(select(Nozzle).where(Nozzle.id==shift.nozzle_id).with_for_update().execution_options(populate_existing=True))
    tank=db.scalar(select(Tank).where(Tank.id==nozzle.tank_id).with_for_update().execution_options(populate_existing=True))
    if shift.litres>tank.stock: raise HTTPException(409,'Insufficient recorded stock; investigate before reconciliation')
    from .operations import movement
    tank.stock-=shift.litres; nozzle.meter=shift.closing; shift.status='reconciled'
    movement(db,tank,-shift.litres,shift.business_date,'shift',str(shift.id),actor.id)
    return save(db,actor,shift,'shift.reconcile')
class DeliveryInput(BaseModel):
    business_date: date = Field(default_factory=lambda: datetime.now(timezone.utc).date())
    tank_id: int
    reference: str = Field(min_length=1,max_length=100)
    supplier: str = Field(min_length=1,max_length=120)
    waybill_litres: Decimal = Field(gt=0,max_digits=14,decimal_places=3)
    received_litres: Decimal = Field(gt=0,max_digits=14,decimal_places=3)
    cost_per_litre: Decimal = Field(gt=0,max_digits=14,decimal_places=4)
@app.post('/deliveries')
def delivery(body: DeliveryInput, db: DB, actor: Actor):
    permit(actor,'owner','manager','supervisor')
    from .operations import writable_day, movement
    t=get(db,Tank,body.tank_id)
    writable_day(db,actor,t.station_id,body.business_date)
    tank=db.scalar(select(Tank).where(Tank.id==body.tank_id).with_for_update().execution_options(populate_existing=True))
    if not tank: raise HTTPException(404,'Tank not found')
    scoped(actor,tank.station_id)
    if db.scalar(select(Delivery).where(Delivery.station_id==tank.station_id,Delivery.reference==body.reference)): raise HTTPException(409,'Delivery already posted')
    if tank.stock+body.received_litres>tank.capacity: raise HTTPException(422,'Delivery exceeds tank capacity')
    tank.stock+=body.received_litres
    delivery=Delivery(station_id=tank.station_id,**body.model_dump()); db.add(delivery); db.flush()
    movement(db,tank,body.received_litres,body.business_date,'delivery',str(delivery.id),actor.id)
    return save(db,actor,delivery,'delivery.post')
class ExpenseInput(BaseModel):
    business_date: date = Field(default_factory=lambda: datetime.now(timezone.utc).date())
    station_id: int
    description: str = Field(min_length=1,max_length=300)
    amount: Decimal = Field(gt=0,max_digits=14,decimal_places=2)
@app.post('/expenses')
def expense(body: ExpenseInput, db: DB, actor: Actor):
    permit(actor,'owner','manager','accountant'); scoped(actor,body.station_id); get(db,Station,body.station_id)
    from .operations import writable_day
    writable_day(db,actor,body.station_id,body.business_date)
    return save(db,actor,Expense(recorded_by=actor.id,**body.model_dump()),'expense.create')
@app.get('/audit')
def audit_list(db: DB, actor: Actor):
    permit(actor,'owner')
    return db.scalars(select(Audit).order_by(Audit.id.desc()).limit(200)).all()

# Register feature routers after the foundational definitions.
from . import operations, security, reporting
app.include_router(operations.router)
app.include_router(security.router)
app.include_router(reporting.router)
security.install(app)
