from flask import Flask, request, jsonify, render_template
from Agent import find_potential_clients
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate-leads', methods=['POST'])
def generate_leads():
    try:
        # Get JSON data from request
        data = request.get_json()
        
        # Check if required fields are present
        if not data or 'industry' not in data or 'country' not in data:
            return jsonify({
                'error': 'Missing required fields. Please provide industry and country.'
            }), 400

        # Extract fields
        industry = data['industry']
        country = data['country']
        requirements = data.get('requirements', '')  # Optional field with empty default

        # Call the find_potential_clients function with additional requirements
        result = find_potential_clients(industry, country, requirements)

        # Return the results
        return jsonify({
            'success': True,
            'filename': result['filename'],
            'table': result['table']
        })

    except Exception as e:
        return jsonify({
            'error': str(e),
            'success': False
        }), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000) 