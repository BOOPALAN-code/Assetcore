# AssetCore Web App

A standalone Asset Management client-server application.

## Prerequisites
- Python 3.x installed on your system.
- No external libraries required (uses standard library).

## How to Run the Server

1. Open your terminal or powershell in this directory.
2. Run the following command:
   ```bash
   python server.py
   ```
3. Open your web browser and go to:
   http://localhost:8000

## Architecture
- **Frontend**: Custom HTML/CSS/JS (Vanilla) located in `public/index.html`. Uses `fetch` to interact with backend.
- **Backend API**: `server.py` handles API requests.
- **Database**: `database.sqlite` generated locally on first use. All state operations are saved in it permanently.
