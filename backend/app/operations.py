"""Credit ledgers, business-day locks, physical stock and maintenance workflows."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, HTTPException
from sqlalchemy import select, func, CheckConstraint, UniqueConstraint, ForeignKey, Numeric, String, Date, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .main import Base, DB, Actor, User, Station, Tank, Product, Nozzle, Shift, Expense, Delivery, get, scoped, permit, save, audit

router=APIRouter()
ZERO=Decimal('0')
def now(): return datetime.now(timezone.utc)
def today(): return now().date()
class FuelPrice(Base):
    __tablename__='fuel_prices'
    id: Mapped[int]=mapped_column(primary_key=True)
    product_id: Mapped[int]=mapped_column(ForeignKey('fuel_products.id'),index=True)
    previous_price: Mapped[Decimal]=mapped_column(Numeric(14,4))
    price: Mapped[Decimal]=mapped_column(Numeric(14,4))
    reason: Mapped[str]=mapped_column(String(500))
    changed_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    valid_from: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class BusinessDay(Base):
    __tablename__='business_days'
    __table_args__=(UniqueConstraint('station_id','business_date'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    business_date: Mapped[date]=mapped_column(Date,index=True)
    status: Mapped[str]=mapped_column(String(20),default='open')
    snapshot: Mapped[dict | None]=mapped_column(JSON)
    revision: Mapped[int]=mapped_column(default=0)
    closed_by: Mapped[int | None]=mapped_column(ForeignKey('users.id'))
    closed_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
class CloseEvent(Base):
    __tablename__='daily_close_events'
    id: Mapped[int]=mapped_column(primary_key=True)
    day_id: Mapped[int]=mapped_column(ForeignKey('business_days.id'))
    action: Mapped[str]=mapped_column(String(20))
    reason: Mapped[str]=mapped_column(String(500))
    snapshot: Mapped[dict]=mapped_column(JSON)
    user_id: Mapped[int]=mapped_column(ForeignKey('users.id'))
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class StockMovement(Base):
    __tablename__='stock_movements'
    __table_args__=(UniqueConstraint('tank_id','source','reference'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    tank_id: Mapped[int]=mapped_column(ForeignKey('tanks.id'),index=True)
    business_date: Mapped[date]=mapped_column(Date,index=True)
    quantity: Mapped[Decimal]=mapped_column(Numeric(14,3))
    source: Mapped[str]=mapped_column(String(30))
    reference: Mapped[str]=mapped_column(String(100))
    recorded_by: Mapped[int | None]=mapped_column(ForeignKey('users.id'))
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class TankReading(Base):
    __tablename__='tank_readings'
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    tank_id: Mapped[int]=mapped_column(ForeignKey('tanks.id'))
    business_date: Mapped[date]=mapped_column(Date,index=True)
    physical: Mapped[Decimal]=mapped_column(Numeric(14,3))
    expected: Mapped[Decimal]=mapped_column(Numeric(14,3))
    variance: Mapped[Decimal]=mapped_column(Numeric(14,3))
    notes: Mapped[str]=mapped_column(String(500))
    recorded_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class Customer(Base):
    __tablename__='customers'
    __table_args__=(CheckConstraint('credit_limit >= 0 AND terms_days >= 0',name='ck_customer_terms'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    name: Mapped[str]=mapped_column(String(120))
    contact: Mapped[str]=mapped_column(String(120))
    credit_limit: Mapped[Decimal]=mapped_column(Numeric(14,2))
    terms_days: Mapped[int]=mapped_column(default=30)
    active: Mapped[bool]=mapped_column(Boolean,default=True)
class Vehicle(Base):
    __tablename__='customer_vehicles'
    __table_args__=(UniqueConstraint('customer_id','registration'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    customer_id: Mapped[int]=mapped_column(ForeignKey('customers.id'),index=True)
    registration: Mapped[str]=mapped_column(String(40))
    fuel_product_id: Mapped[int]=mapped_column(ForeignKey('fuel_products.id'))
    litre_limit: Mapped[Decimal]=mapped_column(Numeric(14,3))
    active: Mapped[bool]=mapped_column(Boolean,default=True)
class CreditCharge(Base):
    __tablename__='credit_transactions'
    __table_args__=(UniqueConstraint('station_id','reference'),CheckConstraint('amount > 0 AND litres > 0',name='ck_credit_positive'))
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    customer_id: Mapped[int]=mapped_column(ForeignKey('customers.id'),index=True)
    shift_id: Mapped[int]=mapped_column(ForeignKey('shifts.id'),index=True)
    vehicle_id: Mapped[int | None]=mapped_column(ForeignKey('customer_vehicles.id'))
    registration: Mapped[str]=mapped_column(String(40))
    driver: Mapped[str]=mapped_column(String(120))
    reference: Mapped[str]=mapped_column(String(100))
    litres: Mapped[Decimal]=mapped_column(Numeric(14,3))
    amount: Mapped[Decimal]=mapped_column(Numeric(14,2))
    business_date: Mapped[date]=mapped_column(Date,index=True)
    due_date: Mapped[date]=mapped_column(Date,index=True)
    recorded_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class CustomerPayment(Base):
    __tablename__='customer_payments'
    __table_args__=(UniqueConstraint('station_id','reference'),CheckConstraint('amount > 0',name='ck_customer_payment_positive'))
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    customer_id: Mapped[int]=mapped_column(ForeignKey('customers.id'),index=True)
    reference: Mapped[str]=mapped_column(String(100))
    method: Mapped[str]=mapped_column(String(30))
    amount: Mapped[Decimal]=mapped_column(Numeric(14,2))
    business_date: Mapped[date]=mapped_column(Date,index=True)
    recorded_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
class PaymentAllocation(Base):
    __tablename__='payment_allocations'
    __table_args__=(UniqueConstraint('payment_id','charge_id'),CheckConstraint('amount > 0',name='ck_allocation_positive'))
    id: Mapped[int]=mapped_column(primary_key=True)
    payment_id: Mapped[int]=mapped_column(ForeignKey('customer_payments.id'))
    charge_id: Mapped[int]=mapped_column(ForeignKey('credit_transactions.id'),index=True)
    amount: Mapped[Decimal]=mapped_column(Numeric(14,2))
class Equipment(Base):
    __tablename__='equipment'
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    name: Mapped[str]=mapped_column(String(120))
    category: Mapped[str]=mapped_column(String(40))
    status: Mapped[str]=mapped_column(String(20),default='operational')
    nozzle_id: Mapped[int | None]=mapped_column(ForeignKey('nozzles.id'),unique=True)
    next_service_date: Mapped[date | None]=mapped_column(Date)
class Maintenance(Base):
    __tablename__='maintenance_records'
    __table_args__=(CheckConstraint('cost >= 0',name='ck_maintenance_cost'),)
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    equipment_id: Mapped[int]=mapped_column(ForeignKey('equipment.id'))
    fault: Mapped[str]=mapped_column(String(500))
    technician: Mapped[str]=mapped_column(String(120))
    status: Mapped[str]=mapped_column(String(30),default='reported')
    repair: Mapped[str]=mapped_column(String(1000),default='')
    cost: Mapped[Decimal]=mapped_column(Numeric(14,2),default=0)
    next_service_date: Mapped[date | None]=mapped_column(Date)
    expense_id: Mapped[int | None]=mapped_column(ForeignKey('expenses.id'))
    reported_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)
    completed_at: Mapped[datetime | None]=mapped_column(DateTime(timezone=True))
class Incident(Base):
    __tablename__='incidents'
    id: Mapped[int]=mapped_column(primary_key=True)
    station_id: Mapped[int]=mapped_column(ForeignKey('stations.id'),index=True)
    category: Mapped[str]=mapped_column(String(60))
    severity: Mapped[str]=mapped_column(String(20))
    description: Mapped[str]=mapped_column(String(1000))
    status: Mapped[str]=mapped_column(String(20),default='open')
    resolution: Mapped[str]=mapped_column(String(1000),default='')
    reported_by: Mapped[int]=mapped_column(ForeignKey('users.id'))
    created: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=now)

def lock_station(db,actor,station_id):
    scoped(actor,station_id)
    station=db.scalar(select(Station).where(Station.id==station_id).with_for_update())
    if not station: raise HTTPException(404,'Station not found')
    return station

def writable_day(db,actor,station_id,day):
    lock_station(db,actor,station_id)
    if day>today(): raise HTTPException(422,'Future business dates are not allowed')
    latest=db.scalar(select(BusinessDay).where(BusinessDay.station_id==station_id).order_by(BusinessDay.business_date.desc()))
    if latest and day<latest.business_date: raise HTTPException(409,'Use the latest business day; historical corrections require a current-day adjustment')
    record=db.scalar(select(BusinessDay).where(BusinessDay.station_id==station_id,BusinessDay.business_date==day))
    if record and record.status=='closed': raise HTTPException(409,'Business day is closed; the owner must reopen it with a reason')
    if not record:
        if latest and latest.status=='open': raise HTTPException(409,'Close the previous business day before opening another')
        record=BusinessDay(station_id=station_id,business_date=day,status='open');db.add(record);db.flush()
    return record

def movement(db,tank,quantity,day,source,reference,user_id):
    db.add(StockMovement(station_id=tank.station_id,tank_id=tank.id,quantity=quantity,business_date=day,source=source,reference=reference,recorded_by=user_id))

def shift_credit(db,id):
    rows=db.scalars(select(CreditCharge).where(CreditCharge.shift_id==id)).all()
    return sum((r.amount for r in rows),ZERO),sum((r.litres for r in rows),ZERO)

def customer_totals(db,id):
    charges=db.scalars(select(CreditCharge).where(CreditCharge.customer_id==id)).all()
    payments=db.scalars(select(CustomerPayment).where(CustomerPayment.customer_id==id)).all()
    paid={cid:amount for cid,amount in db.execute(select(PaymentAllocation.charge_id,func.sum(PaymentAllocation.amount)).group_by(PaymentAllocation.charge_id)).all()}
    invoiced=sum((c.amount for c in charges),ZERO); collected=sum((p.amount for p in payments),ZERO)
    overdue=sum((c.amount-paid.get(c.id,ZERO) for c in charges if c.due_date<today()),ZERO)
    return {'invoiced':invoiced,'paid':collected,'balance':invoiced-collected,'overdue':overdue}

class CustomerInput(BaseModel):
    station_id: int
    name: str=Field(min_length=1,max_length=120)
    contact: str=Field(default='',max_length=120)
    credit_limit: Decimal=Field(ge=0,max_digits=14,decimal_places=2)
    terms_days: int=Field(default=30,ge=0,le=365)
@router.post('/customers')
def create_customer(body: CustomerInput,db:DB,actor:Actor):
    permit(actor,'owner','manager');lock_station(db,actor,body.station_id)
    return save(db,actor,Customer(**body.model_dump()),'customer.create')
@router.get('/customers')
def list_customers(station_id:int,db:DB,actor:Actor):
    scoped(actor,station_id)
    rows=db.scalars(select(Customer).where(Customer.station_id==station_id).order_by(Customer.name)).all()
    if actor.role=='attendant':return [{'id':r.id,'name':r.name,'active':r.active} for r in rows]
    return [{**{c.name:getattr(r,c.name) for c in Customer.__table__.columns},**customer_totals(db,r.id)} for r in rows]
class CreditLimitInput(BaseModel):
    credit_limit: Decimal=Field(ge=0,max_digits=14,decimal_places=2)
    active: bool
    reason: str=Field(min_length=5,max_length=500)
@router.post('/customers/{id}/terms')
def customer_terms(id:int,body:CreditLimitInput,db:DB,actor:Actor):
    permit(actor,'owner');c=get(db,Customer,id);lock_station(db,actor,c.station_id)
    old={'limit':str(c.credit_limit),'active':c.active};c.credit_limit=body.credit_limit;c.active=body.active
    audit(db,actor,'customer.terms',f'{id}; before={old}; after={body.model_dump(mode="json")}');db.commit()
    return {'id':id,'status':'updated'}
class VehicleInput(BaseModel):
    customer_id:int
    registration:str=Field(min_length=1,max_length=40)
    fuel_product_id:int
    litre_limit:Decimal=Field(gt=0,max_digits=14,decimal_places=3)
@router.post('/vehicles')
def create_vehicle(body:VehicleInput,db:DB,actor:Actor):
    permit(actor,'owner','manager');c=get(db,Customer,body.customer_id);lock_station(db,actor,c.station_id)
    if get(db,Product,body.fuel_product_id).station_id!=c.station_id:raise HTTPException(422,'Fuel product belongs to another station')
    return save(db,actor,Vehicle(**body.model_dump()),'vehicle.create')
@router.get('/vehicles')
def vehicles(db:DB,actor:Actor,customer_id:int | None=None,station_id:int | None=None):
    if customer_id:
        c=get(db,Customer,customer_id);scoped(actor,c.station_id)
        return db.scalars(select(Vehicle).where(Vehicle.customer_id==customer_id)).all()
    if station_id is None:raise HTTPException(422,'Choose a station or customer')
    scoped(actor,station_id)
    return db.scalars(select(Vehicle).join(Customer,Customer.id==Vehicle.customer_id).where(Customer.station_id==station_id)).all()
class ChargeInput(BaseModel):
    customer_id:int
    shift_id:int
    vehicle_id:int | None=None
    registration:str=Field(min_length=1,max_length=40)
    driver:str=Field(min_length=1,max_length=120)
    reference:str=Field(min_length=1,max_length=100)
    litres:Decimal=Field(gt=0,max_digits=14,decimal_places=3)
@router.post('/credit/charges')
def charge(body:ChargeInput,db:DB,actor:Actor):
    permit(actor,'owner','manager','supervisor','attendant')
    shift=get(db,Shift,body.shift_id);writable_day(db,actor,shift.station_id,shift.business_date)
    db.refresh(shift)
    if shift.status!='open':raise HTTPException(409,'Credit can only be recorded during an open shift')
    if actor.role=='attendant' and shift.attendant_id!=actor.id:raise HTTPException(403,'Assigned attendant only')
    customer=get(db,Customer,body.customer_id)
    if customer.station_id!=shift.station_id or not customer.active:raise HTTPException(422,'Customer account unavailable at this station')
    amount=(body.litres*shift.price).quantize(Decimal('0.01'))
    if customer_totals(db,customer.id)['balance']+amount>customer.credit_limit:raise HTTPException(409,'Customer credit limit exceeded')
    if body.vehicle_id:
        v=get(db,Vehicle,body.vehicle_id);nozzle=get(db,Nozzle,shift.nozzle_id);tank=get(db,Tank,nozzle.tank_id)
        used=db.scalar(select(func.coalesce(func.sum(CreditCharge.litres),0)).where(CreditCharge.vehicle_id==v.id,CreditCharge.business_date==shift.business_date))
        if v.customer_id!=customer.id or not v.active or v.fuel_product_id!=tank.product_id or v.registration.upper()!=body.registration.upper() or used+body.litres>v.litre_limit:raise HTTPException(422,'Vehicle, fuel or daily vehicle limit is invalid')
    if db.scalar(select(CreditCharge).where(CreditCharge.station_id==shift.station_id,CreditCharge.reference==body.reference)):raise HTTPException(409,'Credit reference already posted')
    return save(db,actor,CreditCharge(station_id=shift.station_id,amount=amount,business_date=shift.business_date,due_date=shift.business_date+timedelta(days=customer.terms_days),recorded_by=actor.id,**body.model_dump()),'credit.charge')
class PaymentInput(BaseModel):
    customer_id:int
    reference:str=Field(min_length=1,max_length=100)
    method:Literal['cash','mtn_momo','telecel_cash','at_money','card','bank_transfer','other']
    amount:Decimal=Field(gt=0,max_digits=14,decimal_places=2)
    business_date:date=Field(default_factory=today)
@router.post('/credit/payments')
def customer_payment(body:PaymentInput,db:DB,actor:Actor):
    permit(actor,'owner','manager','accountant');c=get(db,Customer,body.customer_id)
    writable_day(db,actor,c.station_id,body.business_date)
    if body.amount>customer_totals(db,c.id)['balance']:raise HTTPException(422,'Payment exceeds the outstanding balance')
    if db.scalar(select(CustomerPayment).where(CustomerPayment.station_id==c.station_id,CustomerPayment.reference==body.reference)):raise HTTPException(409,'Payment reference already posted')
    p=CustomerPayment(station_id=c.station_id,recorded_by=actor.id,**body.model_dump());db.add(p);db.flush()
    remaining=body.amount
    charges=db.scalars(select(CreditCharge).where(CreditCharge.customer_id==c.id).order_by(CreditCharge.due_date,CreditCharge.id)).all()
    for ch in charges:
        allocated=db.scalar(select(func.coalesce(func.sum(PaymentAllocation.amount),0)).where(PaymentAllocation.charge_id==ch.id))
        value=min(remaining,ch.amount-allocated)
        if value>0:db.add(PaymentAllocation(payment_id=p.id,charge_id=ch.id,amount=value));remaining-=value
        if remaining==0:break
    return save(db,actor,p,'credit.payment')
@router.get('/customers/{id}/statement')
def statement(id:int,db:DB,actor:Actor):
    permit(actor,'owner','manager','accountant','auditor');c=get(db,Customer,id);scoped(actor,c.station_id)
    rows=[]
    for ch in db.scalars(select(CreditCharge).where(CreditCharge.customer_id==id)).all():rows.append({'date':ch.business_date,'created':ch.created,'kind':'charge','reference':ch.reference,'debit':ch.amount,'credit':ZERO,'due_date':ch.due_date,'vehicle':ch.registration})
    for p in db.scalars(select(CustomerPayment).where(CustomerPayment.customer_id==id)).all():rows.append({'date':p.business_date,'created':p.created,'kind':'payment','reference':p.reference,'debit':ZERO,'credit':p.amount,'due_date':None,'vehicle':''})
    rows.sort(key=lambda r:(r['date'],r['created']));balance=ZERO
    for r in rows:balance+=r['debit']-r['credit'];r['balance']=balance
    return {'customer':c.name,'totals':customer_totals(db,id),'rows':rows}
class DipInput(BaseModel):
    tank_id:int
    physical:Decimal=Field(ge=0,max_digits=14,decimal_places=3)
    notes:str=Field(default='',max_length=500)
    business_date:date=Field(default_factory=today)
@router.post('/tank-readings')
def dip(body:DipInput,db:DB,actor:Actor):
    permit(actor,'owner','manager','supervisor');tank=get(db,Tank,body.tank_id);writable_day(db,actor,tank.station_id,body.business_date)
    db.refresh(tank)
    if body.physical>tank.capacity:raise HTTPException(422,'Physical stock exceeds capacity')
    return save(db,actor,TankReading(station_id=tank.station_id,expected=tank.stock,variance=body.physical-tank.stock,recorded_by=actor.id,**body.model_dump()),'tank.reading')
class AdjustmentInput(DipInput):
    reason:str=Field(min_length=5,max_length=500)
    reference:str=Field(min_length=1,max_length=100)
@router.post('/stock-adjustments')
def adjust(body:AdjustmentInput,db:DB,actor:Actor):
    permit(actor,'owner');tank=get(db,Tank,body.tank_id);writable_day(db,actor,tank.station_id,body.business_date);db.refresh(tank)
    if body.physical>tank.capacity:raise HTTPException(422,'Physical stock exceeds capacity')
    old=tank.stock;movement(db,tank,body.physical-old,body.business_date,'adjustment',body.reference,actor.id);tank.stock=body.physical
    audit(db,actor,'stock.adjust',f'tank={tank.id}; before={old}; after={body.physical}; reason={body.reason}');db.commit()
    return {'tank_id':tank.id,'stock':tank.stock}
@router.get('/expenses')
def expenses(station_id:int,db:DB,actor:Actor):
    permit(actor,'owner','manager','accountant','auditor','supervisor');scoped(actor,station_id)
    return db.scalars(select(Expense).where(Expense.station_id==station_id).order_by(Expense.id.desc()).limit(500)).all()
@router.post('/expenses/{id}/approve')
def approve_expense(id:int,db:DB,actor:Actor):
    permit(actor,'owner','manager');e=get(db,Expense,id);writable_day(db,actor,e.station_id,e.business_date);db.refresh(e)
    if e.status!='pending':raise HTTPException(409,'Expense already approved')
    if actor.role!='owner' and e.recorded_by==actor.id:raise HTTPException(403,'A different manager or the owner must approve this expense')
    e.status='approved';e.approved_by=actor.id;return save(db,actor,e,'expense.approve')

class DayInput(BaseModel):
    station_id:int
    business_date:date=Field(default_factory=today)
    reason:str=Field(default='',max_length=500)
@router.get('/business-days')
def days(station_id:int,db:DB,actor:Actor):
    permit(actor,'owner','manager','supervisor','accountant','auditor');scoped(actor,station_id)
    return db.scalars(select(BusinessDay).where(BusinessDay.station_id==station_id).order_by(BusinessDay.business_date.desc()).limit(100)).all()
@router.post('/daily-close/preview')
def close_preview(body:DayInput,db:DB,actor:Actor):
    permit(actor,'owner','manager','supervisor','accountant','auditor');scoped(actor,body.station_id)
    from .reporting import day_summary, inventory_rows
    blockers=[]
    if db.scalar(select(Shift.id).where(Shift.station_id==body.station_id,Shift.business_date==body.business_date,Shift.status!='reconciled')):blockers.append('Reconcile every shift for this day')
    if db.scalar(select(Expense.id).where(Expense.station_id==body.station_id,Expense.business_date==body.business_date,Expense.status=='pending')):blockers.append('Approve pending expenses')
    for tank in db.scalars(select(Tank).where(Tank.station_id==body.station_id)).all():
        reading=db.scalar(select(TankReading).where(TankReading.tank_id==tank.id,TankReading.business_date==body.business_date).order_by(TankReading.id.desc()))
        last=db.scalar(select(StockMovement).where(StockMovement.tank_id==tank.id,StockMovement.business_date==body.business_date).order_by(StockMovement.id.desc()))
        if not reading or (last and reading.created<last.created):blockers.append(f'Record a fresh closing dip for {tank.name}')
    return {'blockers':blockers,'summary':day_summary(db,body.station_id,body.business_date),'inventory':inventory_rows(db,body.station_id,body.business_date,body.business_date)}
@router.post('/daily-close')
def close_day(body:DayInput,db:DB,actor:Actor):
    permit(actor,'owner','manager');day=writable_day(db,actor,body.station_id,body.business_date)
    snapshot=close_preview(body,db,actor)
    if snapshot['blockers']:raise HTTPException(409, '; '.join(snapshot['blockers']))
    from fastapi.encoders import jsonable_encoder
    day.status='closed';day.snapshot=jsonable_encoder(snapshot);day.closed_at=now();day.closed_by=actor.id;day.revision+=1
    db.add(CloseEvent(day_id=day.id,action='close',reason=body.reason,snapshot=day.snapshot,user_id=actor.id))
    return save(db,actor,day,'day.close')
@router.post('/daily-close/reopen')
def reopen(body:DayInput,db:DB,actor:Actor):
    permit(actor,'owner');lock_station(db,actor,body.station_id)
    if len(body.reason.strip())<5:raise HTTPException(422,'Provide a reason for reopening')
    day=db.scalar(select(BusinessDay).where(BusinessDay.station_id==body.station_id,BusinessDay.business_date==body.business_date))
    latest=db.scalar(select(func.max(BusinessDay.business_date)).where(BusinessDay.station_id==body.station_id))
    if not day or day.status!='closed':raise HTTPException(409,'Day is not closed')
    if day.business_date!=latest:raise HTTPException(409,'Only the latest business day can be reopened; use a current-day adjustment for older periods')
    db.add(CloseEvent(day_id=day.id,action='reopen',reason=body.reason,snapshot=day.snapshot or {},user_id=actor.id));day.status='open'
    audit(db,actor,'day.reopen',f'day={day.id}; reason={body.reason}; revision={day.revision}');db.commit();return day

class EquipmentInput(BaseModel):
    station_id:int
    name:str=Field(min_length=1,max_length=120)
    category:Literal['pump','nozzle','tank','generator','pos','fire_extinguisher','other']
    nozzle_id:int | None=None
    next_service_date:date | None=None
@router.post('/equipment')
def equipment_create(body:EquipmentInput,db:DB,actor:Actor):
    permit(actor,'owner','manager');lock_station(db,actor,body.station_id)
    if body.nozzle_id and get(db,Nozzle,body.nozzle_id).station_id!=body.station_id:raise HTTPException(422,'Nozzle belongs to another station')
    return save(db,actor,Equipment(**body.model_dump()),'equipment.create')
@router.get('/equipment')
def equipment_list(station_id:int,db:DB,actor:Actor):
    scoped(actor,station_id);return db.scalars(select(Equipment).where(Equipment.station_id==station_id)).all()
class MaintenanceInput(BaseModel):
    equipment_id:int
    fault:str=Field(min_length=1,max_length=500)
    technician:str=Field(default='',max_length=120)
@router.post('/maintenance')
def maintenance_create(body:MaintenanceInput,db:DB,actor:Actor):
    permit(actor,'owner','manager','supervisor');e=get(db,Equipment,body.equipment_id);lock_station(db,actor,e.station_id)
    if e.nozzle_id and db.scalar(select(Shift.id).where(Shift.nozzle_id==e.nozzle_id,Shift.status.in_(['open','submitted']))):raise HTTPException(409,'Reconcile the nozzle shift before taking equipment out of service')
    if db.scalar(select(Maintenance.id).where(Maintenance.equipment_id==e.id,Maintenance.status!='completed')):raise HTTPException(409,'Equipment already has an open maintenance job')
    e.status='maintenance';return save(db,actor,Maintenance(station_id=e.station_id,reported_by=actor.id,**body.model_dump()),'maintenance.report')
@router.get('/maintenance')
def maintenance_list(station_id:int,db:DB,actor:Actor):
    scoped(actor,station_id);return db.scalars(select(Maintenance).where(Maintenance.station_id==station_id).order_by(Maintenance.id.desc())).all()
class RepairInput(BaseModel):
    repair:str=Field(min_length=1,max_length=1000)
    technician:str=Field(min_length=1,max_length=120)
    cost:Decimal=Field(ge=0,max_digits=14,decimal_places=2)
    next_service_date:date | None=None
    business_date:date=Field(default_factory=today)
@router.post('/maintenance/{id}/complete')
def complete_maintenance(id:int,body:RepairInput,db:DB,actor:Actor):
    permit(actor,'owner','manager');m=get(db,Maintenance,id);writable_day(db,actor,m.station_id,body.business_date);db.refresh(m)
    if m.status=='completed':raise HTTPException(409,'Maintenance already completed')
    e=get(db,Equipment,m.equipment_id);m.status='completed';m.repair=body.repair;m.technician=body.technician;m.cost=body.cost;m.completed_at=now();m.next_service_date=body.next_service_date
    e.status='operational';e.next_service_date=body.next_service_date
    if body.cost>0:
        expense=Expense(station_id=m.station_id,description=f'Maintenance #{m.id}: {e.name}',amount=body.cost,business_date=body.business_date,recorded_by=actor.id,status='pending');db.add(expense);db.flush();m.expense_id=expense.id
    return save(db,actor,m,'maintenance.complete')
class IncidentInput(BaseModel):
    station_id:int
    category:str=Field(min_length=1,max_length=60)
    severity:Literal['low','medium','high','critical']
    description:str=Field(min_length=1,max_length=1000)
@router.post('/incidents')
def incident_create(body:IncidentInput,db:DB,actor:Actor):
    permit(actor,'owner','manager','supervisor','attendant');lock_station(db,actor,body.station_id)
    return save(db,actor,Incident(reported_by=actor.id,**body.model_dump()),'incident.report')
@router.get('/incidents')
def incident_list(station_id:int,db:DB,actor:Actor):
    scoped(actor,station_id);return db.scalars(select(Incident).where(Incident.station_id==station_id).order_by(Incident.id.desc())).all()
class ResolveInput(BaseModel):
    resolution:str=Field(min_length=1,max_length=1000)
@router.post('/incidents/{id}/resolve')
def incident_resolve(id:int,body:ResolveInput,db:DB,actor:Actor):
    permit(actor,'owner','manager','supervisor');i=get(db,Incident,id);lock_station(db,actor,i.station_id)
    if i.status=='resolved':raise HTTPException(409,'Incident already resolved')
    i.status='resolved';i.resolution=body.resolution;return save(db,actor,i,'incident.resolve')

class PriceInput(BaseModel):
    price:Decimal=Field(gt=0,max_digits=14,decimal_places=4)
    reason:str=Field(min_length=5,max_length=500)
@router.post('/products/{id}/price')
def set_price(id:int,body:PriceInput,db:DB,actor:Actor):
    permit(actor,'owner');product=get(db,Product,id);lock_station(db,actor,product.station_id);db.refresh(product)
    old=product.price
    history=FuelPrice(product_id=id,previous_price=old,price=body.price,reason=body.reason,changed_by=actor.id)
    product.price=body.price;db.add(history)
    audit(db,actor,'price.change',f'product={id}; before={old}; after={body.price}; reason={body.reason}')
    db.commit();return {'product_id':id,'price':product.price,'applies_to':'Newly opened shifts only; existing shifts retain their price snapshot'}
@router.get('/products/{id}/prices')
def prices(id:int,db:DB,actor:Actor):
    permit(actor,'owner','manager','supervisor','accountant','auditor');product=get(db,Product,id);scoped(actor,product.station_id)
    return db.scalars(select(FuelPrice).where(FuelPrice.product_id==id).order_by(FuelPrice.id.desc())).all()
