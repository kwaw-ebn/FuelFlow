# MASTER BUILD PROMPT: FuelFlow Ghana [https://github.com/kwaw-ebn/FuelFlow](https://github.com/kwaw-ebn/FuelFlow)

Act as a senior full-stack software engineer, database architect, UI/UX designer, cybersecurity engineer, and business systems analyst.

Build a production-ready web application called:

**FuelFlow Ghana — Fuel Station Management & Intelligence System**

The system will be used by a fuel filling station in Ghana to manage fuel pumps, tanks, daily sales, attendants, shifts, payments, expenses, fuel deliveries, stock reconciliation, customers, reports, and management oversight.

The system must be simple enough for pump attendants and supervisors to use but powerful enough for the station owner or administrator to monitor the entire business.

## 1. Technology Stack

Build the application using:

**Frontend**

- Next.js
- React
- TypeScript
- Tailwind CSS
- Responsive PWA
- Mobile-first design

**Backend**

- FastAPI
- Python
- REST API

**Database**

- PostgreSQL
- Neon PostgreSQL

**Deployment**

- Frontend: Render
- Backend: Render
- Database: Neon

Use Docker where appropriate.

Use environment variables for secrets and database credentials.

Never hard-code passwords, API keys, database credentials, or payment credentials.

---

# 2. USER ROLES

Implement secure Role-Based Access Control.

### Station Owner / Super Admin

The owner must have access to the entire system.

The owner can:

- View all stations
- View all pumps
- View all tanks
- View real-time operational dashboard
- View sales
- View fuel inventory
- View shifts
- View attendants
- View expenses
- View deliveries
- View payment reconciliation
- View profit estimates
- View reports
- Manage users
- Configure station settings
- Configure fuel prices
- Review audit logs
- Approve adjustments
- Export reports

### Station Manager

Can manage daily station operations but cannot modify critical owner-level settings.

### Supervisor

Can:

- Open shifts
- Close shifts
- Record pump readings
- Verify attendant sales
- Record deliveries
- record expenses
- perform reconciliation
- report incidents

### Pump Attendant

Can only access assigned pumps and shifts.

Can:

- view assigned pump
- enter opening meter
- enter closing meter
- record permitted transactions
- submit shift
- view own shift history

Attendants must not see confidential station-wide financial information.

### Accountant

Can access:

- sales
- expenses
- payment reconciliation
- financial reports
- debtor/customer accounts
- exports

### Auditor

Read-only access to authorized financial, stock, reconciliation, and audit records.

---

# 3. STATION SETUP

Allow the owner to configure:

- Station name
- Station code
- Location
- Region
- District
- GPS coordinates
- Phone
- Email
- Tax/business information
- Number of tanks
- Number of pumps
- Number of nozzles
- Fuel types
- operating hours

Support multiple stations so the platform can eventually become a multi-branch system.

---

# 4. FUEL TYPES

Initially support:

- Petrol
- Diesel

The administrator must be able to add other products later.

Each product should have:

- Product name
- Product code
- Selling price per litre
- Cost price
- Current stock
- Reorder threshold
- Active/inactive status

Fuel prices must be configurable without modifying source code.

Maintain historical fuel prices.

---

# 5. TANK MANAGEMENT

Create a digital tank register.

Each tank should contain:

- Tank ID
- Tank name
- Fuel type
- Maximum capacity
- Current estimated volume
- Minimum safe level
- Reorder level
- Last dip reading
- Last delivery
- Status

Statuses:

- Normal
- Low
- Critical
- Out of stock
- Maintenance

Allow manual tank dip readings.

Store:

- Date
- Time
- Tank
- Dip measurement
- Calculated litres
- Recorded by
- Notes

Maintain complete tank history.

---

# 6. PUMP AND NOZZLE MANAGEMENT

Allow administrators to create:

**Pump**

- Pump number
- Pump name
- Status

Each pump can contain multiple nozzles.

Each nozzle must be linked to:

- Fuel type
- Tank
- Pump
- meter

Example:

Pump 1

- Nozzle A — Petrol
- Nozzle B — Diesel

Track:

- Opening meter reading
- Closing meter reading
- Litres sold
- Selling price
- Expected sales value

Formula:

**Litres Sold = Closing Meter Reading - Opening Meter Reading**

**Expected Revenue = Litres Sold × Applicable Fuel Price**

The applicable fuel price must be the price valid during that shift.

---

# 7. SHIFT MANAGEMENT

Support:

- Morning shift
- Afternoon shift
- Night shift

Allow administrators to create custom shifts.

Each shift must capture:

- Shift ID
- Station
- Date
- Start time
- End time
- Supervisor
- Assigned attendants
- Assigned pumps/nozzles
- Opening readings
- Closing readings
- Litres sold
- Expected revenue
- Amount collected
- Difference
- Notes
- Status

Statuses:

- Pending
- Open
- Submitted
- Under review
- Reconciled
- Closed

Prevent overlapping assignments where appropriate.

---

# 8. SHIFT HANDOVER

Create a structured shift handover workflow.

Outgoing attendant/supervisor records:

- Closing meter readings
- Cash collected
- Mobile Money
- Card/POS
- Credit sales
- expenses or authorized deductions
- incidents
- equipment problems

Incoming shift verifies opening readings.

Maintain both users' identities and timestamps.

Once a shift is reconciled and locked, ordinary users cannot edit it.

Any later correction must require authorization and create an audit record.

---

# 9. SALES RECONCILIATION

Automatically calculate:

**Expected Sales = Litres Sold × Fuel Price**

Calculate:

**Actual Collections = Cash + Mobile Money + Card/POS + Approved Credit + Other Approved Payment**

Then calculate:

**Variance = Actual Collections - Expected Sales**

Show:

- Balanced
- Shortage
- Surplus

Set configurable tolerance limits.

Large discrepancies should automatically create an alert for management.

---

# 10. PAYMENT METHODS

Support:

- Cash
- MTN Mobile Money
- Telecel Cash
- AT Money
- Bank card/POS
- Bank transfer
- Credit/customer account
- Other

Initially, electronic payment entries can be staff-confirmed records.

Design the architecture so real payment gateway integrations can be added later.

Never store card PINs, CVVs, or sensitive payment credentials.

---

# 11. FUEL DELIVERY MANAGEMENT

Create a tanker/fuel delivery module.

Capture:

- Delivery ID
- Date
- Supplier
- Product
- Tanker registration
- Driver
- Waybill number
- Invoice number
- Quantity ordered
- Quantity on waybill
- Tank reading before delivery
- Quantity received
- Tank reading after delivery
- Difference
- Cost per litre
- Total delivery cost
- Received by
- Verified by
- Notes

Allow waybill/invoice attachment.

Calculate delivery variance.

Flag significant shortages.

When an approved delivery is posted, inventory should automatically update.

---

# 12. INVENTORY RECONCILIATION

The system must compare:

**Opening Stock + Deliveries - Recorded Sales = Expected Closing Stock**

Compare this against physical tank/dip stock.

Calculate:

**Stock Variance = Physical Stock - Expected Stock**

Show unexplained losses or gains.

Create alerts when variance exceeds configurable thresholds.

Do not automatically label a variance as theft or fraud. Present it as an exception requiring investigation.

---

# 13. EXPENSE MANAGEMENT

Allow authorized users to record operational expenses.

Categories:

- Electricity
- Generator fuel
- Maintenance
- Cleaning
- Security
- Salaries/wages
- Transport
- Station supplies
- Repairs
- Bank charges
- Other

Capture:

- Date
- Category
- Description
- Amount
- Payment method
- Receipt/reference
- Recorded by
- Approved by
- Attachment

Provide approval workflow for expenses above configurable limits.

---

# 14. CUSTOMER AND CREDIT MANAGEMENT

Create customer accounts for approved credit customers.

Examples:

- Companies
- Schools
- Hospitals
- NGOs
- Government organizations
- Transport companies

Capture:

- Customer name
- Contact
- Company
- Credit limit
- Current balance
- Status

For credit transactions capture:

- Vehicle registration
- Driver
- Fuel type
- Litres
- Amount
- Date
- Authorization/reference
- Attendant
- Pump

Generate statements.

Track:

- Amount invoiced
- Amount paid
- Outstanding balance
- overdue balance

Prevent transactions beyond approved credit limits unless authorized.

---

# 15. VEHICLE/FLEET CUSTOMER MANAGEMENT

For corporate customers, allow registration of approved vehicles.

Capture:

- Registration number
- Vehicle type
- Company
- Driver
- Fuel limit
- permitted fuel type
- status

Generate vehicle fuel consumption history.

---

# 16. STAFF MANAGEMENT

Maintain staff profiles.

Capture:

- Staff ID
- Name
- Role
- Phone
- Email
- Assigned station
- Employment status
- Date joined

Track:

- shifts worked
- pump assignments
- sales handled
- shortages/surpluses
- approvals
- system activity

Do not create simplistic employee rankings based only on sales or shortages.

---

# 17. INCIDENT MANAGEMENT

Allow staff to report:

- Pump malfunction
- Tank issue
- Fuel spill
- Power outage
- POS problem
- Customer complaint
- Safety issue
- suspected transaction anomaly
- Other incident

Capture:

- Incident ID
- Date/time
- Category
- Description
- Severity
- Station
- Pump/tank if relevant
- Reported by
- Assigned to
- Status
- Resolution
- Photos

---

# 18. MAINTENANCE MANAGEMENT

Maintain maintenance records for:

- Pumps
- Nozzles
- Tanks
- Generator
- POS terminals
- Fire extinguishers
- Other station equipment

Capture:

- Equipment
- Fault
- Date reported
- Technician
- Cost
- repair performed
- next service date
- status

Create maintenance reminders.

---

# 19. OWNER DASHBOARD

Create a professional executive dashboard.

Show KPI cards for:

**Today**

- Petrol litres sold
- Diesel litres sold
- Total litres sold
- Expected revenue
- Actual collections
- Sales variance
- Expenses
- Outstanding credit

**Inventory**

- Petrol stock
- Diesel stock
- Estimated days remaining
- Low-stock warnings

**Operations**

- Active shifts
- Pumps operational
- Pumps under maintenance
- Open incidents

Include charts for:

- Daily sales
- Weekly sales
- Monthly sales
- Litres sold by fuel type
- Revenue by fuel type
- Payment method breakdown
- Sales by pump
- Stock movement
- expenses
- reconciliation variance

---

# 20. PROFITABILITY

Where cost data is available, calculate:

Revenue

minus

Fuel Cost

minus

Operating Expenses

equals

Estimated Operating Margin

Show estimated:

- Daily margin
- Weekly margin
- Monthly margin
- Margin by fuel type

Clearly label calculated profitability as an estimate where expenses or cost allocations are incomplete.

---

# 21. ALERT SYSTEM

Create configurable alerts for:

- Low fuel stock
- Critical stock
- Large cash shortage
- Large sales surplus
- Stock variance
- Delivery discrepancy
- Pump malfunction
- overdue customer debt
- unusual adjustment
- shift not closed
- maintenance due

Display alerts on the dashboard.

Support future integration with:

- Email
- SMS
- WhatsApp

---

# 22. REPORTING

Generate professional reports.

### Daily Station Report

Include:

- Opening stock
- Deliveries
- litres sold
- closing stock
- revenue
- cash
- MoMo
- cards
- credit
- expenses
- variance

### Shift Report

Show results by attendant and pump.

### Sales Report

Filter by:

- Date
- Fuel
- Pump
- Nozzle
- Attendant
- Shift
- Payment method

### Inventory Report

Show:

- Opening stock
- deliveries
- sales
- expected stock
- physical stock
- variance

### Expense Report

### Delivery Report

### Credit Customer Report

### Pump Performance Report

### Monthly Management Report

Allow reports to be exported as:

- PDF
- Excel
- CSV

---

# 23. DAILY CLOSE

Create an End-of-Day Close process.

Manager verifies:

- All shifts closed
- Pump readings submitted
- Payments reconciled
- expenses recorded
- deliveries recorded
- stock readings entered

System calculates final daily figures.

After approval, lock the business day.

Corrections after closing must require authorized reopening or adjustment with an audit trail.

---

# 24. AUDIT TRAIL

Maintain an immutable audit trail for important actions.

Record:

- User
- Action
- Date/time
- Previous value
- New value
- IP/device metadata where appropriate
- reason for adjustment

Track actions including:

- meter changes
- fuel price changes
- deleted/cancelled transactions
- expense approvals
- delivery adjustments
- user/role changes
- shift reopening
- stock adjustments

Never permanently erase critical financial records through normal user workflows.

Use reversal/cancellation records where appropriate.

---

# 25. SECURITY

Implement:

- Secure authentication
- Strong password hashing
- JWT/session security
- Role-based authorization
- Station-level data isolation
- Rate limiting
- Input validation
- Secure file uploads
- Database constraints
- Audit logs
- HTTPS in production
- Automatic session timeout
- Account disabling
- password reset
- backup strategy

Require stronger authentication for Owner/Admin accounts.

Design for optional 2FA.

---

# 26. RESPONSIVE DESIGN

The system must work professionally on:

- Desktop
- Laptop
- Tablet
- Smartphone

Pump attendants will frequently use phones.

Keep attendant screens extremely simple.

Example:

**My Shift**

Pump 03
Petrol

Opening Meter: 145,230.40 L

Closing Meter:
[\_\_\_\_\_\_\_\_\_\_\_\_]

Cash:
[\_\_\_\_\_\_\_\_\_\_\_\_]

MoMo:
[\_\_\_\_\_\_\_\_\_\_\_\_]

Card:
[\_\_\_\_\_\_\_\_\_\_\_\_]

Credit:
[\_\_\_\_\_\_\_\_\_\_\_\_]

[SUBMIT SHIFT]

---

# 27. OWNER MOBILE VIEW

Create a simplified owner dashboard optimized for phones.

The owner should be able to open the system and immediately see:

**TODAY**

Sales: GHS XX,XXX

Fuel Sold: X,XXX L

Cash: GHS XX,XXX

MoMo/Card: GHS XX,XXX

Variance: GHS XXX

Petrol Stock: XX,XXX L

Diesel Stock: XX,XXX L

Alerts: X

---

# 28. SEARCH AND FILTERING

Provide search and filters throughout the system.

Allow filtering by:

- Station
- Date
- Shift
- Attendant
- Pump
- Fuel
- Customer
- Payment method
- transaction/reference number

---

# 29. DATABASE DESIGN

Create normalized PostgreSQL tables including:

- organizations
- stations
- users
- roles
- user_station_assignments
- fuel_products
- fuel_prices
- tanks
- tank_readings
- pumps
- nozzles
- shifts
- shift_assignments
- meter_readings
- sales_reconciliations
- payment_collections
- fuel_deliveries
- suppliers
- expenses
- customers
- customer_vehicles
- credit_transactions
- customer_payments
- incidents
- equipment
- maintenance_records
- alerts
- audit_logs
- attachments

Use foreign keys, indexes, timestamps, constraints and appropriate transaction handling.

Never rely only on frontend validation for financial or inventory transactions.

---

# 30. DATA INTEGRITY

This is extremely important.

Prevent:

- Closing meter below opening meter
- Duplicate meter submissions
- Impossible negative fuel stock
- Duplicate delivery posting
- unauthorized price changes
- unauthorized stock adjustments
- unauthorized shift reopening
- deletion of finalized transactions

Use database transactions when posting operations that affect multiple financial or inventory tables.

---

# 31. OPTIONAL FUTURE SMART FEATURES

Design the architecture so later versions can support:

### Automatic Tank Gauge Integration

Automatically obtain tank stock readings from compatible hardware.

### Pump Integration

Automatically obtain pump meter readings where supported.

### Anomaly Detection

Analyze historical data for unusual:

- sales variances
- stock losses
- pump patterns
- delivery discrepancies

The AI must flag patterns for human review rather than automatically accusing staff of misconduct.

### Demand Forecasting

Predict expected petrol and diesel demand.

### Reorder Intelligence

Estimate when the station will need another delivery.

### Multi-Station Intelligence

Allow an owner with several stations to compare operations across branches.

---

# 32. USER EXPERIENCE

Use a modern professional interface.

Main navigation:

Dashboard

Sales & Shifts

Pumps

Tanks & Inventory

Deliveries

Customers & Credit

Expenses

Staff

Maintenance

Incidents

Reports

Alerts

Audit Log

Settings

Use cards, tables, charts, status badges, modals, confirmation dialogs and responsive navigation.

Do not overcrowd the dashboard.

---

# 33. DEVELOPMENT REQUIREMENTS

Build this as a real working application, not a static UI prototype.

Provide:

1. Complete project architecture
2. Frontend
3. Backend
4. PostgreSQL schema
5. Database migrations
6. Authentication
7. RBAC
8. API endpoints
9. Dashboard
10. Pump management
11. Tank management
12. Shift management
13. Sales reconciliation
14. Deliveries
15. Expenses
16. Credit management
17. Reports
18. Audit trail
19. Seed/demo data
20. Docker configuration
21. `.env.example`
22. README
23. Neon setup instructions
24. Render deployment instructions
25. Production security checklist

Do not use mock data for the final production workflows.

Seed/demo data can be provided separately for testing.

---

# 34. BUILD ORDER

Develop the system incrementally.

### Phase 1 — Foundation

Database, authentication, RBAC, station setup and users.

### Phase 2 — Fuel Infrastructure

Products, tanks, pumps, nozzles and pricing.

### Phase 3 — Operations

Shifts, attendants, meter readings and handovers.

### Phase 4 — Finance

Sales reconciliation, payments and expenses.

### Phase 5 — Inventory

Tank readings, deliveries and stock reconciliation.

### Phase 6 — Management

Dashboards, alerts, reports and daily close.

### Phase 7 — Commercial Accounts

Customers, vehicles and credit management.

### Phase 8 — Advanced Operations

Maintenance, incidents, attachments and audit controls.

### Phase 9 — Deployment

Neon PostgreSQL + Render frontend/backend.

### Phase 10 — Future Intelligence

Forecasting, anomaly detection and hardware integrations.

Before implementing each phase, inspect the existing codebase and database so new work does not break completed functionality.

Create production-quality code, meaningful error handling, validation, tests and documentation.

The final result should function as a complete digital control centre for managing a modern fuel station.
