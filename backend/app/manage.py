"""Versioned migrations and secure, interactive installation/recovery commands."""
import argparse, getpass
from pathlib import Path
from sqlalchemy import select, inspect
from alembic import command
from alembic.config import Config
from .main import Base, engine, SessionLocal, User, hash_password, audit
parser=argparse.ArgumentParser()
parser.add_argument('command',choices=['migrate','owner','recover-owner'])
parser.add_argument('--email')
parser.add_argument('--name',default='Station Owner')
args=parser.parse_args()
if args.command=='migrate':
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    tables=set(inspect(engine).get_table_names())
    legacy={'stations','users','fuel_products','tanks','nozzles','shifts','fuel_deliveries','expenses','audit_logs'}
    if tables and 'alembic_version' not in tables:
        if tables!=legacy or 'session_version' in {c['name'] for c in inspect(engine).get_columns('users')}:raise SystemExit('Unversioned schema is not the known v0.1 schema. Back up and inspect before migrating.')
        command.stamp(config,'0001')
    command.upgrade(config,'head');print('Schema upgraded to the latest version.')
else:
    if not args.email:parser.error('--email is required')
    password=getpass.getpass('Password (minimum 12 characters): ')
    if len(password)<12:raise SystemExit('Password too short')
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email==args.email.lower()))
        if args.command=='owner':
            if db.scalar(select(User.id).where(User.role=='owner')):raise SystemExit('An owner already exists; use recovery for an existing owner.')
            user=User(email=args.email.lower(),name=args.name,password=hash_password(password),role='owner');db.add(user);db.flush();audit(db,user,'owner.cli_create','Initial owner created using database administrator access')
        else:
            if not user or user.role!='owner':raise SystemExit('Owner account not found')
            reason=input('Reason for owner recovery: ').strip()
            if len(reason)<5:raise SystemExit('A reason is required')
            user.password=hash_password(password);user.session_version+=1;user.mfa_enabled=False;user.mfa_secret=None
            from .security import RecoveryCode,MFAReplay
            db.query(RecoveryCode).filter(RecoveryCode.user_id==user.id).delete(synchronize_session=False)
            db.query(MFAReplay).filter(MFAReplay.user_id==user.id).delete(synchronize_session=False)
            audit(db,user,'owner.cli_recover',reason)
        db.commit();print('Owner account saved. Sign in and enroll two-factor authentication.')
