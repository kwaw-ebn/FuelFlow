from datetime import date, timedelta
from decimal import Decimal
import io, pyotp
from sqlalchemy import select
from test_operations import setup
from app.main import Tank, User
from app.operations import BusinessDay, Customer, StockMovement, PaymentAllocation
from app.security import cipher, AuthSession

def open_shift(c,owner):
    r=c.post('/shifts',headers=owner,json={'nozzle_id':1,'attendant_id':2});assert r.status_code==200,r.text;return r.json()['id']
def customer(c,owner,limit=200):
    r=c.post('/customers',headers=owner,json={'station_id':1,'name':'Fleet Co','contact':'0240000000','credit_limit':limit,'terms_days':0});assert r.status_code==200,r.text;return r.json()['id']
def test_credit_account_and_reconciliation_no_double_count(setup):
    c,maker,owner,attendant=setup;id=open_shift(c,owner);cid=customer(c,owner)
    body={'customer_id':cid,'shift_id':id,'registration':'GR1234','driver':'Kofi','reference':'CR1','litres':10}
    assert c.post('/credit/charges',headers=attendant,json=body).status_code==200
    assert c.post('/credit/charges',headers=attendant,json=body).status_code==409
    body.update(reference='CR2',litres=5)
    assert c.post('/credit/charges',headers=attendant,json=body).status_code==409
    assert c.post(f'/shifts/{id}/submit',headers=attendant,json={'closing':1005,'cash':0,'momo':0,'card':0}).status_code==422
    r=c.post(f'/shifts/{id}/submit',headers=attendant,json={'closing':1010,'cash':0,'momo':0,'card':0});assert r.status_code==200 and Decimal(r.json()['variance'])==0
    assert c.post(f'/shifts/{id}/reconcile',headers=owner).status_code==200
    p={'customer_id':cid,'amount':100,'method':'mtn_momo','reference':'PAY1'}
    assert c.post('/credit/payments',headers=owner,json=p).status_code==200
    assert c.post('/credit/payments',headers=owner,json=p).status_code in [409,422]
    assert c.post('/credit/payments',headers=owner,json={**p,'reference':'PAY2','amount':60}).status_code==422
    statement=c.get(f'/customers/{cid}/statement',headers=owner).json();assert Decimal(statement['totals']['balance'])==55
    summary=c.get('/dashboard?station_id=1',headers=owner).json();assert Decimal(summary['expected'])==155 and Decimal(summary['collections'])==0 and Decimal(summary['customer_debt_payments'])==100
    assert c.get(f'/customers/{cid}/statement',headers=attendant).status_code==403

def test_daily_close_requires_dips_and_pending_expense_approval(setup):
    c,maker,owner,attendant=setup;id=open_shift(c,owner)
    body={'station_id':1}
    assert c.post('/daily-close',headers=owner,json=body).status_code==409
    assert c.post(f'/shifts/{id}/submit',headers=attendant,json={'closing':1010,'cash':155,'momo':0,'card':0}).status_code==200
    assert c.post(f'/shifts/{id}/reconcile',headers=owner).status_code==200
    eid=c.post('/expenses',headers=owner,json={'station_id':1,'description':'Power','amount':10}).json()['id']
    assert c.post('/tank-readings',headers=owner,json={'tank_id':1,'physical':489}).status_code==200
    assert c.post('/daily-close',headers=owner,json=body).status_code==409
    assert c.post(f'/expenses/{eid}/approve',headers=owner).status_code==200
    r=c.post('/daily-close',headers=owner,json=body);assert r.status_code==200,r.text
    assert c.post('/expenses',headers=owner,json={'station_id':1,'description':'Late expense','amount':2}).status_code==409
    assert c.post('/daily-close/reopen',headers=owner,json={**body,'reason':'x'}).status_code==422
    assert c.post('/daily-close/reopen',headers=attendant,json={**body,'reason':'Correction'}).status_code==403
    assert c.post('/daily-close/reopen',headers=owner,json={**body,'reason':'Add omitted receipt'}).status_code==200
    assert c.post('/expenses',headers=owner,json={'station_id':1,'description':'Late expense','amount':2}).status_code==200

def test_maintenance_and_exports(setup):
    c,maker,owner,attendant=setup
    eid=c.post('/equipment',headers=owner,json={'station_id':1,'name':'Nozzle A','category':'nozzle','nozzle_id':1}).json()['id']
    mid=c.post('/maintenance',headers=owner,json={'equipment_id':eid,'fault':'Leaking hose','technician':'Ama'}).json()['id']
    assert c.post('/shifts',headers=owner,json={'nozzle_id':1,'attendant_id':2}).status_code==409
    assert c.post(f'/maintenance/{mid}/complete',headers=owner,json={'repair':'Hose replaced','technician':'Ama','cost':20,'next_service_date':str(date.today()+timedelta(days=90))}).status_code==200
    assert c.post(f'/maintenance/{mid}/complete',headers=owner,json={'repair':'Duplicate','technician':'Ama','cost':20}).status_code==409
    assert c.get('/expenses?station_id=1',headers=owner).json()[0]['status']=='pending'
    for fmt,magic in [('csv',b'\xef\xbb\xbf'),('xlsx',b'PK'),('pdf',b'%PDF')]:
        r=c.get(f'/reports/maintenance/export?station_id=1&format={fmt}',headers=owner);assert r.status_code==200,r.text;assert r.content.startswith(magic)
    assert c.get('/reports/sales?station_id=2',headers=attendant).status_code==403
    assert c.get('/reports/sales?station_id=1&start=2020-01-01&end=2026-10-01',headers=owner).status_code==422

def test_logout_password_revocation_and_account_disable(setup):
    c,maker,owner,attendant=setup
    assert c.post('/auth/logout',headers=attendant).status_code==200
    assert c.get('/auth/me',headers=attendant).status_code==401
    token=c.post('/auth/login',json={'email':'attendant@test.com','password':'secure-password'}).json()['access_token'];a={'Authorization':'Bearer '+token}
    assert c.post('/staff/2/access',headers=owner,json={'active':False,'reason':'Employment ended'}).status_code==200
    assert c.get('/auth/me',headers=a).status_code==401
    assert c.post('/auth/login',json={'email':'attendant@test.com','password':'secure-password'}).status_code==401
    assert c.post('/auth/password',headers=owner,json={'current_password':'secure-password','new_password':'new-secure-password'}).status_code==200
    assert c.get('/auth/me',headers=owner).status_code==401

def test_owner_mfa_enrollment_recovery_and_throttle(setup,monkeypatch):
    c,maker,owner,_=setup;monkeypatch.setenv('REQUIRE_OWNER_MFA','true')
    login=c.post('/auth/login',json={'email':'owner@test.com','password':'secure-password'}).json();assert login['mfa_enrollment_required']
    restricted={'Authorization':'Bearer '+login['access_token']}
    assert c.get('/stations',headers=restricted).status_code==403
    r=c.post('/auth/mfa/setup',headers=restricted,json={'password':'secure-password'});assert r.status_code==200
    value=r.json()['secret'];otp=pyotp.TOTP(value).now()
    confirmed=c.post('/auth/mfa/confirm',headers=restricted,json={'otp':otp});assert confirmed.status_code==200,confirmed.text
    recovery=confirmed.json()['recovery_codes'][0]
    assert c.get('/stations',headers={'Authorization':'Bearer '+confirmed.json()['access_token']}).status_code==200
    assert c.post('/auth/login',json={'email':'owner@test.com','password':'secure-password'}).status_code==401
    assert c.post('/auth/login',json={'email':'owner@test.com','password':'secure-password','otp':recovery}).status_code==200
    assert c.post('/auth/login',json={'email':'owner@test.com','password':'secure-password','otp':recovery}).status_code==401
    from app.operations import now
    frozen=now();monkeypatch.setattr('app.security.now',lambda:frozen)
    for _ in range(8):response=c.post('/auth/login',json={'email':'owner@test.com','password':'wrong'})
    assert response.status_code==429

def test_price_authorization_and_report_formula_protection(setup):
    c,maker,owner,attendant=setup;sid=open_shift(c,owner)
    assert c.post('/products/1/price',headers=attendant,json={'price':20,'reason':'Price revision'}).status_code==403
    assert c.post('/products/1/price',headers=owner,json={'price':20,'reason':'Price revision'}).status_code==200
    assert Decimal(c.get('/shifts?station_id=1',headers=owner).json()[0]['price'])==Decimal('15.5')
    assert c.get('/products/1/prices',headers=owner).json()[0]['reason']=='Price revision'
    assert c.post('/expenses',headers=owner,json={'station_id':1,'description':'=HYPERLINK("bad")','amount':10}).status_code==200
    r=c.get('/reports/expenses/export?station_id=1&format=csv',headers=owner);assert b"'=HYPERLINK" in r.content
    r=c.get('/reports/expenses/export?station_id=1&format=xlsx',headers=owner)
    from openpyxl import load_workbook
    workbook=load_workbook(io.BytesIO(r.content));cell=workbook.active['C2'];assert cell.data_type=='s' and cell.value.startswith("'=")
    assert c.post(f'/shifts/{sid}/submit',headers=attendant,json={'closing':1010,'cash':155,'momo':0,'card':0}).status_code==200
    assert c.post(f'/shifts/{sid}/reconcile',headers=owner).status_code==200
    rows=c.get('/reports/management?station_id=1',headers=owner).json()['rows'];assert rows[0]['estimated_operating_margin'] is None
