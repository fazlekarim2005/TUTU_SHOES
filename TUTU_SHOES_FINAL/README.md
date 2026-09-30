# TUTU SHOES — Final Flask + MySQL Web App

A complete local-first e-commerce website and admin panel for TUTU SHOES.

## Included

- Customer product catalogue
- Search and category/gender filters
- Product details
- Cart with multiple items
- Checkout (prepaid test mode)
- Server-side order creation
- Stock deduction when an order is created
- Admin login with hashed password
- Admin dashboard
- Product add/edit/activate/deactivate
- Product search/category/gender/status filters
- Order list and status management
- Courier/tracking fields
- Responsive UI
- MySQL schema

## Before running

1. Install MySQL Server.
2. Create a Python virtual environment.
3. Install requirements:
   `pip install -r requirements.txt`
4. Copy `.env.example` to `.env`.
5. Put your MySQL password in `.env`.
6. Start:
   `python app.py`

The app creates the database/tables automatically if the MySQL user has permission.

## First admin

Open:
`http://127.0.0.1:5000/setup-admin`

Create the Owner Admin once, then delete/disable the setup route before production.

## Important production work before going live

- Use HTTPS.
- Use a strong secret key.
- Remove/disable `/setup-admin`.
- Connect the shop owner's official Razorpay merchant account.
- Implement Razorpay server-side verification/webhooks.
- Add proper CSRF protection.
- Use production WSGI hosting.
- Configure backups.
- Move image storage to Cloudinary/S3-style storage.
- Add real courier integration or keep manual courier/tracking entry.
- Review privacy/terms/refund/shipping policies.

This package intentionally uses simulated prepaid payment so no merchant credentials are embedded.
