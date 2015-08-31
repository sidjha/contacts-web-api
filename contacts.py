from flask import Flask, render_template, request, json, jsonify, make_response, abort
import os, re, binascii, gzip, base64, hmac, hashlib, math, random

from parse_rest.datatypes import Object
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import register

import twilio
from twilio.rest import TwilioRestClient

import boto

app = Flask(__name__)
app.config.from_object("config")
app.config["DEBUG"] = True

register(app.config["PARSE_APP_ID"], app.config["PARSE_RESTAPI_KEY"])


@app.route("/")
def index():
	return "API v1"

@app.errorhandler(404)
def not_found(error):
	return make_response(jsonify({"error": "Not found"}), 404)

@app.errorhandler(400)
def bad_request(error):
	return make_response(jsonify({"error": "Bad request"}), 400)

@app.errorhandler(405)
def not_allowed(error):
	return make_response(jsonify({"error": "Method Not Allowed"}), 405)

@app.errorhandler(500)
def internal_server(error):
	return make_response(jsonify({"error": "A Whale! Something went wrong!"}), 500)


"""
  Resource URL: https://favor8api.herokuapp.com/favor8/api/v1.0/ver-codes/generate
  Type: POST
  Requires Authentication? No
  Response formats: JSON
  Parameters
   phone (required): The phone number to verify. e.g. +14161234567
  Example request:
   POST https://favor8api.herokuapp.com/favor8/api/v1.0/ver-codes/generate?phone=+14161234567
  Example response:
   {"code": "444213", "phone":"+14161234567"}
"""
@app.route("/favor8/api/v1.0/ver-codes/generate", methods=["POST"])
def sms_verify():
	if not request.json or not "phone" in request.json:
		abort(400)
	
	phone = request.json["phone"]
	try:
		code = generate_code(phone)
	except:
		print_error("Something went wrong with sending code in email")
		abort(500)

	unverified_user = None
	try:
		# Update/create unverified user to store a (phone number, code) pair
		unverified_user = UnverifiedUser.Query.get(phoneNum=phone)
		unverified_user.ver_code = code
		unverified_user.save()
		print_debug("Saved phone number successfully.")
	except QueryResourceDoesNotExist:
		unverified_user = UnverifiedUser(phone=phone, ver_code=code)
	
	try:
		unverified_user.save()
	except Exception as e:
		print_error("There was a problem saving unverified user to DB")
		abort(500)

	sent = send_sms(code, phone)

	if sent == True:
		return jsonify({"code": code, "phone": phone}), 200
	else:
		abort(500)


"""
  Resource URL: https://favor8api.herokuapp.com/favor8/api/v1.0/ver-codes/verify
  Type: GET
  Requires Authentication? No
  Response formats: JSON
  Parameters
   submitted_code (required): The code to verify. e.g. 434512
   phone (required): The phone number associated with the code e.g. +14161234567
  Example request:
   GET https://favor8api.herokuapp.com/ver-codes/verify?submitted_code=434512&phoneNum=+14161234567
  Example response:
   {"match": "True"}
"""
@app.route("/favor8/api/v1.0/ver-codes/verify", methods=["GET"])
def check_ver_code():
	if not request.json or not all(k in request.json for k in ("code", "phone")):
		print_error("phone and code required.")
		abort(400)

	try:
		unverified_user = UnverifiedUser.Query.get(phone=request.json["phone"])
		actual_code = unverified_user.ver_code
		if actual_code != request.json["code"]:
			print_debug("Codes don't match.")
			abort(400)
	except QueryResourceDoesNotExist:
		print_error("Code has expired.")
		abort(404)

	try:
		new_user = User(phone=request.json["phone"], smsVerified=True)
		new_user.save()
		return jsonify({"match":"True", "id_str": new_user.objectId}), 200
	except:
		abort(500)


def generate_code(phone_num):
	code = str(random.randint(100000,999999))

	# Temp hack to forward to sid@mesh8.co
	from postmark import PMMail
	message = PMMail(api_key = app.config["POSTMARK_API_TOKEN"],
	                 subject = "Verification Code from Favor8",
	                 sender = "sid@mesh8.co",
	                 to = "sid@mesh8.co",
	                 text_body = "Your Favor8 verification code is %s" % code,
	                 tag = "favor8")

	message.send()
	return code


def send_sms(code, phone_num):
	sms_body = "Hey there, your verification code is %s" % code
	sent = False

	try:
		client = TwilioRestClient(app.config["TWILIO_TEST_ACCOUNT_SID"], app.config["TWILIO_TEST_AUTH_TOKEN"])
		message = client.messages.create(body=sms_body,to=phone_num,from_=app.config["TWILIO_TEST_FROM_NUM"])
		return True

	except twilio.TwilioRestException as e:
		return False



# Classes

class User(Object):
	pass

class UnverifiedUser(Object):
	pass


# Helpers

def print_error(error_msg):
	if app.config["DEBUG"] == True:
		print "ERROR: %s" % error_msg


def print_debug(msg):
	if app.config["DEBUG"] == True:
		print msg


if __name__ == "__main__":
	app.run()