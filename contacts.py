from flask import Flask, render_template, request, json
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


""" 
  Resource URL: https://favor8api.herokuapp.com/account/register
  Type: POST
  Requires Authentication? No
  Response formats: JSON
  Parameters
   name (required): The full name of the user. E.g. Siddharth Jha
   user_key (required): A unique identification key, such as email address or phone number. E.g. +919812345678
  Example request: 
   POST https://favor8api.herokuapp.com/account/register?name=Siddharth%20Jha&user_key=9812345678
  Example response:
   {"id_str": "h2dJrEjKWJ", "name": "Siddharth Jha", "user_key": "9812345678"}
"""
@app.route("/account/register", methods=["POST"])
def account_register():
	if request.method == "POST":

		name = ""
		user_key = ""
		user = None

		if "name" in request.form:
			name = request.form["name"]
		if "user_key" in request.form:
			user_key = request.form["user_key"]
			user_key = user_key.strip()
		if name.strip() == "" or user_key == "":
			error = "ERROR: Incomplete arguments. name and user_key required."
			print_error(error)
			return json.dumps({"error": error}), 400

		try:
			user = User.Query.get(key=user_key)
			error = "ERROR: User already exists."
			print_error(error)
			return json.dumps({"error": error}), 400
 		except Exception as e:
			user = User()
			print_debug("New user created %s" % user)

		try:
			print user
			user.name = name
			user.key = user_key
			user.save()
			return json.dumps({"name":user.name, "user_key":user.key, "id_str":user.objectId}), 200
		except Exception as e:
			error = "ERROR: User could not be added to database"
			print_error(error)
			return json.dumps({"error": error}), 500

	else:
		return only_post_supported()


"""
  Resource URL: https://favor8api.herokuapp.com/account/sms-verify
  Type: POST
  Requires Authentication? No
  Response formats: JSON
  Parameters
   phone (required): The phone number to verify. e.g. +14161234567
  Example request:
   POST https://favor8api.herokuapp.com/account/sms-verify?phone=+14161234567
  Example response:
   {"code": "444213", "phone":"+14161234567"}
"""
@app.route("/account/sms-verify", methods=["POST"])
def sms_verify():
	if request.method == "POST":
		phone = ""
		# TODO: Get country from request
		if "phone" in request.form:
			phone = request.form["phone"]
		else:
			error = "ERROR: Incomplete arguments. phone required."
			print_error(error)
			return json.dumps({"error": error}), 400

		code = generate_code(phone)

		try:
			unverified_user = UnverifiedUser.Query.get(phoneNum=phone)
			print unverified_user
			#import pdb; pdb.set_trace()
			unverified_user.ver_code = int(code)
			unverified_user.save()
			print "Saved phone number successfully."
		except QueryResourceDoesNotExist:
			new_unverified_user = UnverifiedUser(phoneNum=phone, country="", ver_code=int(code))
			new_unverified_user.save()

		sent = send_sms(code, phone)

		if sent == True:
			verification_code = {}
			verification_code["code"] = code
			verification_code["phone"] = phone
			return json.dumps({"code": code, "phone": phone}), 200
		else:
			error = "ERROR: Verification SMS could not be sent"
			print_error(error)
			return json.dumps({"error": error}), 500


"""
  Resource URL: https://favor8api.herokuapp.com/account/code-verify
  Type: GET
  Requires Authentication? No
  Response formats: JSON
  Parameters
   submitted_code (required): The code to verify. e.g. 434512
   phoneNum (required): The phone number associated with the code e.g. +14161234567
  Example request:
   GET https://favor8api.herokuapp.com/account/code-verify?submitted_code=434512&phoneNum=+14161234567
  Example response:
   {"match": "True"}
"""
@app.route("/account/code-verify", methods=["GET"])
def check_ver_code():
	submitted_code = ""
	phone = ""

	try:
		submitted_code = request.args.get("submitted_code")
		phone = request.args.get("phoneNum")
	except Exception as e:
		error = "ERROR: Incomplete arguments. phone required."
		print_error(error)
		return json.dumps({"error": error}), 400

	try:
		unverified_user = UnverifiedUser.Query.get(phoneNum=phone)
		actual_code = str(unverified_user.ver_code)
		if actual_code == submitted_code:
			resp = {}
			resp["match"] = "True"
			# TODO: also append phone # to response
			return json.dumps({"match":"True"}), 200
		else:
			print "codes don't match"
			resp = {}
			resp['match'] = "False"
			return json.dumps({"match": "False"}), 400

	except QueryResourceDoesNotExist:
		error = "ERROR: Couldn't find unverified user with that phone"
		print_error(error)
		return json.dumps({"error": error}), 400


def generate_code(phone_num):
	code = str(random.randint(100000,999999))

	print "Verification code: %s" % code

	try:
		from postmark import PMMail
		message = PMMail(api_key = app.config["POSTMARK_API_TOKEN"],
		                 subject = "Verification Code from Favor8",
		                 sender = "sid@mesh8.co",
		                 to = "sid@mesh8.co,pankaj.xcode@gmail.com",
		                 text_body = "Your Favor8 verification code is %s" % code,
		                 tag = "favor8")

		message.send()
		return code
	except:
		return "000001"
	


def send_sms(code, phone_num):
	sms_body = "Hey there, your verification code is %s" % code
	sent = False

	try:
		client = TwilioRestClient(app.config["TWILIO_TEST_ACCOUNT_SID"], app.config["TWILIO_TEST_AUTH_TOKEN"])
		message = client.messages.create(body=sms_body,to=phone_num,from_=app.config["TWILIO_TEST_FROM_NUM"])
		print "Sent SMS to %s" % phone_num
		print "SMS_contents: %s" % sms_body
		return True

	except twilio.TwilioRestException as e:
		return False


""" 
  Resource URL: https://favor8api.herokuapp.com/cards/update
  Type: POST
  Requires Authentication? Yes
  Response formats: JSON
  Parameters
   id_str (required): ObjectId of the user obtained at registration. E.g. h2dJrEjKWJ
   name (optional): The full name of the user. E.g. Siddharth Jha
   profile_img (optional): A base64-encoded image representing user's profile picture.
   accounts (optional): A dictionary with social accounts of the user. E`.g. {"WhatsApp":"+919812345678", "Kik": "john9"}
   status (optional): A short status message. E.g. Just arrived in Mumbai.
  Example request: 
   POST https://favor8api.herokuapp.com/cards/update?name=Mark%20Zuckerberg&id_str=g534fb4fu7&accounts={"facebook":"zuck", "whatsapp":"+14159989989"}
  Example response:
   {"id_str": "g534fb4fu7", "name": "Mark Zuckerberg", "user_key": "+14159989989", "profile_img": "http://s3.amazonaws.com/23e23rf3e3f/h2.jpg", 
    "accounts":{"facebook": "zuck", "whatsapp": "+14159989989"}, "status":"A short status message."}
"""
@app.route("/cards/update", methods=["POST"])
def update_card():
	if request.method == "POST":
		id_str = ""
		name = ""
		profile_img = None
		accounts = {}
		status = ""
		user = None

		if "id_str" not in request.form:
			error = "ERROR: Incomplete arguments. id_str required."
			print_error(error)
			return json.dumps({"error": error}), 400
		else:
			id_str = request.form["id_str"]
			try:
				user = User.Query.get(objectId=id_str)
			except Exception as e:
				error = "ERROR: Invalid user. Please check id_str."
				print_error(error)
				return json.dumps({"error": error}), 400

			if "name" in request.form:
				name = request.form["name"]
				user.name = name
			if "profile_img" in request.form:
				profile_img_base64 = request.form["profile_img"]

				try:
					img_base64_data = re.search("base64,(.*)", profile_img_base64)
					decoded_img = img_base64_data.group(1)

					NUM_SUFFIX_CHARS = 10
					img_filename = id_str + "-" + binascii.b2a_hex(os.urandom(NUM_SUFFIX_CHARS)) + ".png"

					tempfile = open(img_filename, "wb")
					tempfile.write(decoded_img.decode('base64'))
					tempfile.close()

					from boto.s3.key import Key
					s3_conn = boto.connect_s3(app.config["AWS_ACCESS_KEY"], app.config["AWS_SECRET"])
					s3_bucket = s3_conn.get_bucket(app.config["S3_BUCKET_NAME_PROFILEPICS"])
					s3_key = img_filename
					s3_k = Key(s3_bucket)
					s3_k.key = s3_key
					s3_k.set_contents_from_filename(s3_key)
					s3_k.set_acl("public-read")

					os.remove(img_filename)

					profile_img = "https://" + app.config["S3_BUCKET_NAME_PROFILEPICS"] + ".s3.amazonaws.com/" + img_filename
					user.profile_img = profile_img
				except Exception as e:
					error = "ERROR: Something went wrong in saving profile image to server.."
					print_error(error)
					return json.dumps({"error": error}), 500

			if "status" in request.form:
				status = request.form["status"]
				user.status = status
			if "accounts" in request.form:
				accounts = json.loads(request.form["accounts"])
				user.accounts = accounts

			try:
				import pdb; pdb.set_trace()
				user.save()
				return json.dumps({"id_str":user.objectId, "name": user.name, "profile_img": profile_img, "accounts": accounts, "status": status}), 200
			except Exception as e:
				error = "ERROR: Card update could not be saved."
				print_error(error)
				return json.dumps({"error": error}), 500
	else:
		return only_post_supported()


# Stubs
@app.route("/cards/update_status", methods=["POST"])
def account_update_status():
	if request.method == "POST":
		user = None
		if "user_object_id" in request.form:
			try:
				user = User.query.get(objectId=request.form["user_object_id"])
			except Exception as e:
				return user_does_not_exist()
			try:
				if "status" in request.form:
					user.status = request.form["status"]
					# TODO: validation
				return json.dumps({"successMsg": "Status successfully updated"}), 200
			except Exception as e:
				error = "ERROR: Status could not be updated"
				print_error(error)
				return json.dumps({"error": error}), 500
	else:
		return only_post_supported()

@app.route("/cards/update_links", methods=["POST"])
def update_links():
	pass


@app.route("/cards/my_stack", methods=["GET"])
def my_stack():
	pass


@app.route("/cards/show/id", methods=["GET"])
def show_card():
	pass


@app.route("/cards/nearby", methods=["GET"])
def show_nearby_cards():
	pass


@app.route("/friends/list", methods=["GET"])
def friend_list():
	pass


@app.route("/friendships/create", methods=["POST"])
def create_friendship():
	pass


@app.route("/friendships/update", methods=["POST"])
def update_friendship():
	pass


@app.route("/friendships/destroy", methods=["POST"])
def destroy_friendship():
	pass


@app.route("/friendships/show", methods=["GET"])
def show_friendship():
	pass



# Classes

class User(Object):
	pass

class UnverifiedUser(Object):
	pass


# Helpers

def print_error(error):
	if app.config["DEBUG"] == True:
		print error


def print_debug(msg):
	if app.config["DEBUG"] == True:
		print msg


def only_post_supported():
	error = "ERROR: Bad request. This method only supports POST"
	if app.config["DEBUG"] == True:
		print error
	return json.dumps({"error": error}), 400


def user_does_not_exist():
	error = "ERROR: That user does not exist"
	print_error(error)
	return json.dumps({"error": error}), 400


if __name__ == "__main__":
	app.run()