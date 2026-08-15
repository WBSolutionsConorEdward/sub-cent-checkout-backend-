import os
import requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

# Configuration loaded from Render environment variables
NOWPAYMENTS_API_KEY = os.environ.get("NOWPAYMENTS_API_KEY")
IPN_SECRET_KEY = os.environ.get("IPN_SECRET_KEY")


def get_optimal_payment_method(country_code):
  """Maps user region to the most optimal, lowest-cost local payment rail."""
  routes = {
      "US": "ACH Bank Transfer / Local Card On-Ramp (Lowest US Fee)",
      "AU": "POLi / PayID / Local Bank Transfer via On-Ramp",
      "GB": "UK Faster Payments / Local Transfer",
      "DE": "SEPA Instant Bank Transfer (Lowest EU Fee)",
      "FR": "SEPA Instant Bank Transfer (Lowest EU Fee)",
  }
  return routes.get(country_code, "Global Credit Card / Direct Crypto Transfer")


@app.route("/", methods=["GET"])
def home():
  # Looks for templates/index.html
  return render_template("index.html")


@app.route("/create-payment", methods=["POST"])
def create_payment():
  try:
    # 1. Track user region automatically from cloud proxy headers
    user_country = (
        request.headers.get("CF-IPCountry")
        or request.headers.get("X-Vercel-IP-Country")
        or "US"
    )

    # 2. Get optimal payment rail recommendation
    optimal_rail = get_optimal_payment_method(user_country)

    data = request.json or {}
    price_amount = data.get("amount", 20.00)

    # 3. Request NOWPayments to create an invoice/payment
    headers = {
        "x-api-key": NOWPAYMENTS_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {
        "price_amount": price_amount,
        "price_currency": "usd",
        "pay_currency": "usdttrc20",
        "order_description": "Growth Suite Order",
    }

    response = requests.post(
        "https://api.nowpayments.io/v1/payment", json=payload, headers=headers
    )
    res_data = response.json()

    if response.status_code != 200:
      return jsonify({
          "error": "Failed to create payment with NOWPayments",
          "details": res_data,
      }), 400

    # 4. Return combined data to frontend
    return jsonify({
        "success": True,
        "detected_country": user_country,
        "recommended_payment_rail": optimal_rail,
        "payment_id": res_data.get("payment_id"),
        "pay_address": res_data.get("pay_address"),
        "pay_amount": res_data.get("pay_amount"),
        "pay_currency": res_data.get("pay_currency"),
        "payment_status": res_data.get("payment_status"),
    })

  except Exception as e:
    return jsonify({"error": str(e)}), 500


@app.route("/ipn-listener", methods=["POST"])
def ipn_listener():
  ipn_data = request.json
  if not ipn_data:
    return "No data received", 400

  payment_status = ipn_data.get("payment_status")
  order_id = ipn_data.get("order_id")

  print(
      f"Received IPN Update for Order {order_id}: Status -> {payment_status}"
  )

  if payment_status == "finished":
    print("Payment successfully completed and verified!")

  return jsonify({"status": "acknowledged"}), 200


if __name__ == "__main__":
  port = int(os.environ.get("PORT", 5000))
  app.run(host="0.0.0.0", port=port)