import hashlib
import hmac
import json
import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import requests

app = Flask(__name__)
CORS(app)  # Enables communication between your GitHub website and Render backend

# --- CONFIGURATION ---
API_KEY = os.environ.get("NOWPAYMENTS_API_KEY", "2RYH2YR-C5EMT8K-H06GDGB-TWJYFH3")
IPN_SECRET_KEY = os.environ.get(
    "IPN_SECRET_KEY", "CfB8wGW0A+IdU4RztEEZ/ILi2bOVmwhS"
)
BASE_URL = "https://api.nowpayments.io/v1"


def create_payment(
    price_amount, price_currency, pay_currency, ipn_url, order_id, order_desc
):
  url = f"{BASE_URL}/payment"

  payload = json.dumps({
      "price_amount": price_amount,
      "price_currency": price_currency,
      "pay_currency": pay_currency,
      "pay_amount": price_amount,  # <--- Forces crypto amount to match fiat input exactly
      "ipn_callback_url": ipn_url,
      "order_id": order_id,
      "order_description": order_desc,
  })

  headers = {"x-api-key": API_KEY, "Content-Type": "application/json"}

  try:
    response = requests.post(url, headers=headers, data=payload)
    return response.json()
  except requests.exceptions.RequestException as e:
    return {"error": str(e)}


def verify_ipn_signature(secret_key, received_signature, message_dict):
  sorted_msg = json.dumps(message_dict, separators=(",", ":"), sort_keys=True)

  digest = hmac.new(
      str(secret_key).encode("utf-8"),
      sorted_msg.encode("utf-8"),
      hashlib.sha512,
  )
  computed_signature = digest.hexdigest()

  return hmac.compare_digest(computed_signature, received_signature)


@app.route("/create-payment", methods=["POST"])
def api_create_payment():
  data = request.get_json() or {}

  price_amount = data.get("price_amount", 10.0)
  price_currency = data.get("price_currency", "usd")
  pay_currency = data.get("pay_currency", "usdttrc20")
  order_id = data.get("order_id", "WILLCO-123")
  order_desc = data.get("order_description", "Custom Service Invoice")

  ipn_url = "https://sub-cent-checkout-backend.onrender.com/ipn-listener"

  result = create_payment(
      price_amount,
      price_currency,
      pay_currency,
      ipn_url,
      order_id,
      order_desc,
  )
  return jsonify(result)


@app.route("/ipn-listener", methods=["POST"])
def ipn_listener():
  received_signature = request.headers.get("x-nowpayments-sig")

  if not received_signature:
    return jsonify({"error": "No signature provided"}), 400

  try:
    request_data = request.get_json()
  except Exception:
    return jsonify({"error": "Invalid JSON payload"}), 400

  if not verify_ipn_signature(IPN_SECRET_KEY, received_signature, request_data):
    return jsonify({"error": "HMAC signature does not match"}), 403

  payment_status = request_data.get("payment_status")
  payment_id = request_data.get("payment_id")
  outcome_amount = request_data.get("outcome_amount")

  print(
      f"Received valid IPN -> Payment ID: {payment_id}, Status:"
      f" {payment_status}"
  )

  if payment_status == "finished":
    print(
        f"SUCCESS: Payment {payment_id} finished. Outcome amount:"
        f" {outcome_amount}"
    )

  return jsonify({"status": "success"}), 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port, debug=True)