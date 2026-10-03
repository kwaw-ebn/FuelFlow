import os
os.environ['JWT_SECRET']='test-only-secret-not-for-live-use-123456789'
from decimal import Decimal
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app, db, Base, User, Station, Product, Tank, Nozzle, Shift, hash_password
@pytest.fixture
def setup():
    test_url=os.getenv('TEST_DATABASE_URL')
    schema=None;admin=None
    if test_url:
        from sqlalchemy.engine import make_url
        from sqlalchemy import text
        from uuid import uuid4
        if not make_url(test_url).database.startswith('fuelflow_test'):raise RuntimeError('Use a dedicated fuelflow_test database')
        schema='test_'+uuid4().hex;admin=create_engine(test_url)
        with admin.begin() as c:c.execute(text(f'CREATE SCHEMA {schema}'))
        engine=create_engine(test_url,connect_args={'options':'-csearch_path='+schema})
    else:engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    from alembic import command
    from alembic.config import Config
    from pathlib import Path
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    with engine.begin() as connection:
        config.attributes['connection']=connection
        command.upgrade(config,'head')
    maker=sessionmaker(engine,expire_on_commit=False)
    with maker() as s:
        s.add_all([Station(id=1,name='Pilot',code='P1',region='Central',district='Agona East'),Station(id=2,name='Other',code='P2',region='Central',district='Other')]);s.flush()
        s.add_all([User(id=1,email='owner@test.com',name='Owner',password=hash_password('secure-password'),role='owner'),User(id=2,email='attendant@test.com',name='Attendant',password=hash_password('secure-password'),role='attendant',station_id=1)]);s.flush()
        s.add(Product(id=1,station_id=1,name='Petrol',price=Decimal('15.5')));s.flush()
        s.add(Tank(id=1,station_id=1,product_id=1,name='Tank',capacity=1000,stock=500,reorder=100));s.flush()
        s.add(Nozzle(id=1,station_id=1,tank_id=1,name='Pump 1 A',meter=1000));s.flush()
        from app.operations import StockMovement, today
        s.add(StockMovement(station_id=1,tank_id=1,business_date=today(),quantity=500,source='opening',reference='1'));s.commit()
    def override():
        with maker() as s: yield s
    app.dependency_overrides[db]=override
    with TestClient(app) as c:
        def auth(email):
            r=c.post('/auth/login',json={'email':email,'password':'secure-password'});assert r.status_code==200
            return {'Authorization':'Bearer '+r.json()['access_token']}
        yield c,maker,auth('owner@test.com'),auth('attendant@test.com')
    app.dependency_overrides.clear()
    engine.dispose()
    if admin:
        with admin.begin() as c:c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin.dispose()
def test_reconciliation_and_snapshot(setup):
    c,maker,owner,attendant=setup
    r=c.post('/shifts',headers=owner,json={'nozzle_id':1,'attendant_id':2});assert r.status_code==200
    id=r.json()['id']
    assert c.post('/shifts',headers=owner,json={'nozzle_id':1,'attendant_id':2}).status_code==409
    with maker() as s: s.get(Product,1).price=20;s.commit()
    assert c.post(f'/shifts/{id}/submit',headers=attendant,json={'closing':999,'cash':0,'momo':0,'card':0}).status_code==422
    r=c.post(f'/shifts/{id}/submit',headers=attendant,json={'closing':1010,'cash':100,'momo':55,'card':0})
    assert r.status_code==200 and Decimal(r.json()['expected'])==155
    assert c.post(f'/shifts/{id}/submit',headers=attendant,json={'closing':1011,'cash':1,'momo':0,'card':0}).status_code==409
    assert c.post(f'/shifts/{id}/reconcile',headers=attendant).status_code==403
    assert c.post(f'/shifts/{id}/reconcile',headers=owner).status_code==200
    assert c.post(f'/shifts/{id}/reconcile',headers=owner).status_code==409
    with maker() as s:
        assert s.get(Tank,1).stock==490
        assert s.get(Nozzle,1).meter==1010

def test_station_isolation(setup):
    c,_,owner,attendant=setup
    assert c.get('/inventory?station_id=2',headers=attendant).status_code==403
    assert c.get('/dashboard?station_id=1',headers=attendant).status_code==403
    assert c.get('/audit',headers=attendant).status_code==403

def test_delivery_and_negative_stock(setup):
    c,maker,owner,_=setup
    body={'tank_id':1,'reference':'WB1','supplier':'Supplier','waybill_litres':100,'received_litres':90,'cost_per_litre':12}
    assert c.post('/deliveries',headers=owner,json=body).status_code==200
    assert c.post('/deliveries',headers=owner,json=body).status_code==409
    body.update(reference='WB2',received_litres=500)
    assert c.post('/deliveries',headers=owner,json=body).status_code==422
    id=c.post('/shifts',headers=owner,json={'nozzle_id':1,'attendant_id':2}).json()['id']
    assert c.post(f'/shifts/{id}/submit',headers=owner,json={'closing':1700,'cash':10850,'momo':0,'card':0}).status_code==200
    assert c.post(f'/shifts/{id}/reconcile',headers=owner).status_code==409
    with maker() as s:
        assert s.get(Tank,1).stock==590
        assert s.get(Shift,id).status=='submitted'
