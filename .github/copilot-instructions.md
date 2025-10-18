# Osakedata Web Viewer Project

This is a Flask web application that provides a browser interface for viewing stock data from SQLite database:
- **Flask** for web framework
- **pandas** for data manipulation  
- **SQLite** for data storage

## Project Structure
- `main.py` - Flask web application
- `templates/index.html` - Web UI template
- `requirements.txt` - Python dependencies
- `README.md` - Project documentation
- `.gitignore` - Git ignore patterns

## Database Location
The application reads from: `/home/kalle/projects/rawcandle/data/osakedata.db`

## Usage
Run the web application with:
```bash
/home/kalle/projects/test/.venv/bin/python main.py
```

Then open browser to: `http://localhost:5000`

## Features
- Web interface for searching stock data
- Support for single or multiple stock symbols (comma-separated)
- Display available symbols in database
- Responsive Bootstrap UI
- Data displayed in sortable tables
- Search by clicking available symbol badges

## Development
The project uses a Python virtual environment located in `.venv/` with Flask and pandas installed.