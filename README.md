# Leads generator

This is a leads generator that uses AI to find potential clients for a given industry and country.

## Usage
-Set enviorment variable
```bash
export TAVILY_API_KEY=your_api_key
export OPENAI_API_KEY=your_api_key
```

-Install dependencies
```bash
pip install -r requirements.txt
```
-Run the app
```bash
python app.py
```

navigate to http://localhost:5000/

the generation will be saved in projects root directory in a directory called leads (which is an MD table file)

you can also save the output in excel format by saving export to excel button on the UI