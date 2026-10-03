"""Posting races run against the isolated PostgreSQL service in CI."""
import os
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import pytest
from test_operations import setup
from app.main import Tank
pytestmark=pytest.mark.skipif(not os.getenv('TEST_DATABASE_URL'),reason='Requires dedicated PostgreSQL test database')
def test_parallel_reconciliation_cannot_spend_same_tank_stock(setup):
    c,maker,owner,attendant=setup
    n2=c.post('/nozzles',headers=owner,json={'tank_id':1,'name':'Nozzle B','meter':2000}).json()['id']
    first=c.post('/shifts',headers=owner,json={'nozzle_id':1,'attendant_id':2}).json()['id']
    second=c.post('/shifts',headers=owner,json={'nozzle_id':n2,'attendant_id':2}).json()['id']
    for id,closing in [(first,1400),(second,2400)]:assert c.post(f'/shifts/{id}/submit',headers=attendant,json={'closing':closing,'cash':6200,'momo':0,'card':0}).status_code==200
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda id:c.post(f'/shifts/{id}/reconcile',headers=owner).status_code,[first,second]))
    assert sorted(results)==[200,409]
    with maker() as db:assert db.get(Tank,1).stock==100

def test_parallel_credit_sales_cannot_exceed_customer_limit(setup):
    c,maker,owner,attendant=setup
    cid=c.post('/customers',headers=owner,json={'station_id':1,'name':'Fleet','credit_limit':200}).json()['id']
    sid=c.post('/shifts',headers=owner,json={'nozzle_id':1,'attendant_id':2}).json()['id']
    def charge(reference):return c.post('/credit/charges',headers=attendant,json={'customer_id':cid,'shift_id':sid,'reference':reference,'registration':'GR123','driver':'Kofi','litres':10}).status_code
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(charge,['RACE1','RACE2']))
    assert sorted(results)==[200,409]
    rows=c.get('/customers?station_id=1',headers=owner).json();assert Decimal(rows[0]['balance'])==155
