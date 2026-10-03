"""Installation CLI. No automatic account or demo data creation."""
import argparse, getpass
from sqlalchemy import select
from .main import Base, engine, SessionLocal, User, hash_password
parser=argparse.ArgumentParser()
parser.add_argument('command',choices=['migrate','owner'])
parser.add_argument('--email')
parser.add_argument('--name',default='Station Owner')
args=parser.parse_args()
if args.command=='migrate':
    Base.metadata.create_all(engine)
    print('Initial schema created. This command does not upgrade existing columns.')
else:
    if not args.email: parser.error('--email is required')
    password=getpass.getpass('Owner password (minimum 12 characters): ')
    if len(password)<12: raise SystemExit('Password too short')
    with SessionLocal() as db:
        if db.scalar(select(User).where(User.email==args.email.lower())): raise SystemExit('Account already exists')
        db.add(User(email=args.email.lower(),name=args.name,password=hash_password(password),role='owner'))
        db.commit()
    print('Owner created.')
