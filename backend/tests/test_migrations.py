from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.exc import DBAPIError
import pytest

def test_legacy_upgrade_preserves_records_and_enforces_history(tmp_path):
    engine=create_engine('sqlite:///'+str(tmp_path/'legacy.db'))
    config=Config(str(Path(__file__).resolve().parents[1]/'alembic.ini'))
    with engine.begin() as c:
        config.attributes['connection']=c;command.upgrade(config,'0001')
        c.execute(text("INSERT INTO stations (id,name,code,region,district) VALUES (1,'Legacy','LEG','Central','Agona East')"))
        c.execute(text("INSERT INTO users (id,email,name,password,role,active) VALUES (1,'owner@example.com','Owner','hash','owner',1)"))
        c.execute(text("INSERT INTO fuel_products (id,station_id,name,price) VALUES (1,1,'Petrol',15.5)"))
        c.execute(text("INSERT INTO tanks (id,station_id,product_id,name,capacity,stock,reorder) VALUES (1,1,1,'Tank 1',1000,500,100)"))
        c.execute(text("INSERT INTO expenses (id,station_id,description,amount,created) VALUES (1,1,'Legacy bill',20,'2026-09-15 12:00:00')"))
        c.execute(text("INSERT INTO fuel_deliveries (id,station_id,tank_id,reference,supplier,waybill_litres,received_litres,cost_per_litre) VALUES (1,1,1,'WB-OLD','Supplier',100,100,10)"))
        command.upgrade(config,'head')
    with engine.connect() as c:
        assert c.scalar(text('SELECT stock FROM tanks WHERE id=1'))==500
        assert c.scalar(text('SELECT quantity FROM stock_movements WHERE tank_id=1'))==500
        row=c.execute(text('SELECT business_date,status FROM expenses WHERE id=1')).one();assert row[0]=='2026-09-15' and row[1]=='approved'
        assert c.scalar(text('SELECT session_version FROM users WHERE id=1'))==0
        assert c.scalar(text('SELECT business_date FROM fuel_deliveries WHERE id=1')) is not None
    with engine.begin() as c:c.execute(text("INSERT INTO audit_logs (user_id,action,details,created) VALUES (1,'test','history',CURRENT_TIMESTAMP)"))
    with pytest.raises(DBAPIError):
        with engine.begin() as c:c.execute(text("UPDATE audit_logs SET details='changed'"))
    with pytest.raises(DBAPIError):
        with engine.begin() as c:c.execute(text('DELETE FROM stock_movements'))
    # Repeated startup migrations are harmless.
    with engine.begin() as c:config.attributes['connection']=c;command.upgrade(config,'head')
