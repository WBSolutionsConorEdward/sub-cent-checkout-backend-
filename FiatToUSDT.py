import json
import hmac
import hashlib
from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

# --- CONFIGURATION ---
# Replace these placeholders with your actual NOWPayments credentials
API_KEY = "2RYH2YR-C5EMT8K-H06GDGB-TWJYFH3"
IPN_SECRET_KEY = "Us/aiULnnsM232G42Qc9YWiuE6tQsokQ"
BASE_URL = "https://api.nowpayments.io/v1"

def create_payment(price_amount, price_currency, pay_currency, ipn_url, order_id):
    """
    Creates a payment invoice via NOWPayments API.
    """
    url = f"{BASE_URL}/payment"
    
    payload = json.dumps({
        "price_amount": price_amount,
        "price_currency": price_currency,
        "pay_currency": pay_currency,
        "ipn_callback_url": ipn_url,
        "order_id": order_id
    })
    
    headers = {
        'x-api-key': API_KEY,
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(url, headers=headers, data=payload)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def verify_ipn_signature(secret_key, received_signature, message_dict):
    """
    Validates the incoming NOWPayments IPN signature using HMAC-SHA512.
    Sorts keys alphabetically as required by NOWPayments.
    """
    sorted_msg = json.dumps(message_dict, separators=(',', ':'), sort_keys=True)
    
    digest = hmac.new(
        str(secret_key).encode('utf-8'),
        sorted_msg.encode('utf-8'),
        hashlib.sha512
    )
    computed_signature = digest.hexdigest()
    
    return hmac.compare_digest(computed_signature, received_signature)

@app.route('/create-payment', methods=['POST'])
def api_create_payment():
    """
    Endpoint for your frontend to request a payment creation.
    """
    data = request.get_json() or {}
    
    price_amount = data.get('price_amount', 10.0)
    price_currency = data.get('price_currency', 'usd')
    pay_currency = data.get('pay_currency', 'btc')
    order_id = data.get('order_id', 'ORDER-123')
    
    # Replace with your public server URL (e.g., your live deployment URL)
    ipn_url = "https://your-backend-app.onrender.com/ipn-listener"
    
    result = create_payment(price_amount, price_currency, pay_currency, ipn_url, order_id)
    return jsonify(result)

@app.route('/ipn-listener', methods=['POST'])
def ipn_listener():
    """
    Webhook endpoint to receive and process Instant Payment Notifications (IPN).
    """
    received_signature = request.headers.get('x-nowpayments-sig')
    
    if not received_signature:
        return jsonify({"error": "No signature provided"}), 400
        
    try:
        request_data = request.get_json()
    except Exception:
        return jsonify({"error": "Invalid JSON payload"}), 400
        
    # Verify the HMAC signature for security
    if not verify_ipn_signature(IPN_SECRET_KEY, received_signature, request_data):
        return jsonify({"error": "HMAC signature does not match"}), 403
        
    # Extract safe parameters
    payment_status = request_data.get('payment_status')
    payment_id = request_data.get('payment_id')
    outcome_amount = request_data.get('outcome_amount')
    
    print(f"Received valid IPN -> Payment ID: {payment_id}, Status: {payment_status}")
    
    # Core fulfillment logic: Fulfill ONLY when status is 'finished'
    if payment_status == 'finished':
        print(f"SUCCESS: Payment {payment_id} finished. Outcome amount: {outcome_amount}")
        # TODO: Update your database to grant goods/services/balance here
        
    elif payment_status == 'partially_paid':
        print(f"WARNING: Payment {payment_id} was partially paid.")
        # TODO: Handle partial payment logic if needed
        
    return jsonify({"status": "success"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)