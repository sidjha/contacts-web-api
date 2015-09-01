from flask import Flask, render_template, request, json, jsonify, make_response, abort
import os, re, binascii, gzip, base64, hmac, hashlib, math, random

from parse_rest.datatypes import Object
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import register

import twilio
from twilio.rest import TwilioRestClient

import boto
import analytics

app = Flask(__name__)
app.config.from_object("config")
app.config["DEBUG"] = True

register(app.config["PARSE_APP_ID"], app.config["PARSE_RESTAPI_KEY"])


@app.route("/")
def index():
	abort(401, "Invalid permissions.")

@app.errorhandler(400)
def bad_request(error):
	return make_response(jsonify({"error": error.description}), 400)

@app.errorhandler(401)
def internal_server(error):
	return make_response(jsonify({"error": error.description}), 401)

@app.errorhandler(404)
def not_found(error):
	return make_response(jsonify({"error": error.description}), 404)

@app.errorhandler(405)
def not_allowed(error):
	return make_response(jsonify({"error": error.description}), 405)

@app.errorhandler(500)
def internal_server(error):
	return make_response(jsonify({"error": error.description}), 500)




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
def api_vercodes_generate():
	if not request.json or not "phone" in request.json:
		abort(400, "Missing parameter.")
	
	phone = request.json["phone"]
	try:
		code = generate_code(phone)
	except:
		errmsg = "Something went wrong with sending code via email."
		print_error(errmsg)
		abort(500, errmsg) # TODO: Remove this abort

	unverified_user = None
	try:
		# Update/create unverified user to store a (phone number, code) pair
		unverified_user = UnverifiedUser.Query.get(phone=phone)
		unverified_user.ver_code = code
		unverified_user.save()
		print_debug("Saved phone number successfully.")
	except QueryResourceDoesNotExist:
		unverified_user = UnverifiedUser(phone=phone, ver_code=code)
	
	try:
		unverified_user.save()
	except Exception as e:
		errmsg = "There was a problem saving unverified user to DB"
		print_error(errmsg)
		abort(500, errmsg)

	sent = send_sms(code, phone)

	if sent == True:
		return jsonify({"code": code, "phone": phone}), 200
	else:
		errmsg = "Verification SMS could not be sent."
		print_error(errmsg)
		abort(500, errmsg)


"""
  Resource URL: https://favor8api.herokuapp.com/favor8/api/v1.0/ver-codes/verify
  Type: GET
  Requires Authentication? No
  Parameters
   code (required): The code to verify. e.g. 434512
   phone (required): The phone number associated with the code e.g. +14161234567
  Example response:
   {"match": true}
"""
@app.route("/favor8/api/v1.0/ver-codes/verify", methods=["POST"])
def api_vercodes_verify():
	if not request.json or not dict_contains_fields(request.json, ["code", "phone"]):
		errmsg = "Missing parameters."
		print_error(errmsg)
		abort(400, errmsg)

	unverified_user = None
	try:
		unverified_user = UnverifiedUser.Query.get(phone=request.json["phone"])
		actual_code = unverified_user.ver_code
		if actual_code != request.json["code"]:
			errmsg = "Codes don't match."
			print_debug(errmsg)
			abort(400, errmsg)
	except QueryResourceDoesNotExist:
		errmsg = "Code has expired"
		print_debug(errmsg)
		abort(404, errmsg)

	unverified_user.delete()
	return jsonify({"match":True}), 200


""" 
  Resource URL: //favor8/api/v1.0/users/create
  Type: POST
  Requires Authentication? No
  Parameters:
   username (required): username, can be alphanumeric, max 20 characters. String.
   password (required): a password, can be alphanumeric and contain special characters. String.
  Example response:
   {"user_id": "2", "auth_token": "avsdf232332we32r32r!2323223"}
"""
@app.route("/favor8/api/v1.0/users/create", methods=["POST"])
def api_users_create():
	if not request.json or not dict_contains_fields(request.json, ["username", "password"]):
		abort(400, "Missing parameters.")
	username = request.json["username"]
	# TODO: hash password
	password = request.json["password"]

	try:
		User.Query.get(username=username)
		print_error("User already exists")
		abort(400, "User already exists")
	except QueryResourceDoesNotExist:
		pass
	
	try:
		new_user_id = User.Query.all().count() + 1
		auth_token = generate_auth_token(new_user_id)
		user = User(username=username, password=password, auth_token=auth_token, user_id=new_user_id)
		print "New user created. %s, %s" % (username, user)
		user.save()
	except Exception as e:
		errmsg = "New user could not be saved."
		print_error(errmsg)
		abort(500, errmsg)
	
	try:
		user_for_analytics = {}
		user_for_analytics["username"] = user.username
		user_for_analytics["user_id"] = user.user_id
		user_for_analytics["via"] = "username/password"
		analytics.new_user_signed_up(user_for_analytics)
	except:
		pass
	return jsonify({"user_id":user.user_id, "auth_token":user.auth_token}), 200

""" 
  Resource URL: //favor8/api/v1.0/users/login-fb
  Type: POST
  Requires Authentication? No
  Parameters:
   fb-token (required): The FB auth token, can be alphanumeric, max 20 characters. String. e.g. johnnycash
   email address (required): Email address associated with facebook account. String. e.g. johnnycash@example.com
   fb-id (required): The facebook ID of the person. String. e.g. 166344
  Example response:
   {"name": "Johnny Cash", "username": "johnny", "auth_token": "avsdf232332we32r32r!2323223"}
"""
@app.route("/favor8/api/v1.0/users/login-via-fb", methods=["POST"])
def api_login_via_fb():
	pass


@app.route("/favor8/api/v1.0/users/login", methods=["POST"])
def api_user_login():
	""" 
	  Resource URL: //favor8/api/v1.0/users/login
	  Type: POST
	  Requires Authentication? No
	  Parameters:
	   username (required): username. String.
	   password (required): password. String.
	  Example response:
	   {"username": "johnny", "auth_token": "avsdf232332we32r32r!2323223"}
	"""
	if not request.json or not dict_contains_fields(request.json, ["username", "password"]):
		abort(400, "Missing parameters.")
	username = request.json["username"]
	password = request.json["password"]

	user = None
	try:
		user = User.Query.get(username=username)
	except QueryResourceDoesNotExist:
		print_error("That user does not exist.")
		abort(404, "That user does not exist.")

	if user.password != password:
		abort(401, "Incorrect password.")

	auth_token = generate_auth_token(user.user_id)

	try:
		user.auth_token = auth_token
		user.save()
	except:
		print_error("ERROR: New Auth token could not be saved to user.")
		abort(500, "New auth token could not be saved.")

	try:
		user_for_analytics = {}
		user_for_analytics["username"] = user.username
		user_for_analytics["user_id"] = user.user_id
		user_for_analytics["via"] = "username/password"
		analytics.user_logged_in(user_for_analytics)
	except:
		pass

	return jsonify({"username":user.username, "auth_token":auth_token, "user_id": user.user_id}), 200


@app.route("/favor8/api/v1.0/users/show/<int:user_id>", methods=["GET"])
def api_show_user(user_id):
	""" 
	  Returns a user's data.
	  Resource URL: //favor8/api/v1.0/users/show
	  Type: GET
	  Requires Authentication? No
	  Parameters:
	   user_id (required): user ID of user. Numeric.
	   auth_token (required): an active authorization token for the authenticating user. String.
	  Example response:
	   {"user_id": 133, "username": "johnny" "name": "Johnny Cash", "phone": "+14159989989", "profile_img": "http://s3.amazonaws.com/23e23rf3e3f/h2.jpg", 
	    "accounts":{"facebook": "zuck", "whatsapp": "+14159989989"}, "status":"A short status message."}
	"""
	if not request.json or not dict_contains_fields(request.json, ["auth_token"]):
		abort(400, "Invalid parameters.")

	auth_token = request.json["auth_token"]
	# TODO: validate auth_token properly

	auth_user = User.Query.get(user_id=decode_id_from_auth_token(auth_token))
	if auth_user.auth_token != auth_token:
		abort(401, "Invalid auth token.")

	return_friends = True
	if user_id != auth_user.user_id: # if card data of another user is being requested
		return_friends = False
		friends = auth_user.friends
		if user_id not in auth_user.friends: # permission check
			abort(400, "Don't have permission to access this user's data.")

	user = None
	try:
		user = User.Query.get(user_id=user_id)
	except:
		abort(400, "User not found.")

	return jsonify(user_card(user, return_friends)), 200


@app.route("/favor8/api/v1.0/users/update", methods=["POST"])
def api_update_user():
	""" 
	  Update authenticating user's data.
	  Resource URL: //favor8/api/v1.0/users/update
	  Type: POST
	  Requires Authentication? Yes
	  Parameters:
	   auth_token (required): an active authorization token for this user. String.
	   data: A dictionary containing user data.
	   	profile_img: A base64-encoded image representing user's profile picture. String.
	   	name: The full name of the user. String. E.g. Johnny Cash
	   	social_links: A dictionary with social accounts of the user. Dictionary. E.g. {"WhatsApp":"+919812345678", "Kik": "john9"}
	   	status: A short status message. String. E.g. Just arrived in Mumbai.
	   	email: An email. String.
	   	phone: Phone #. String.
	  Example response:
	   {"error": "Some of the data could not be saved.", "user": {"user_id": 5, "username": "johnny" "name": "Johnny Cash", "phone": "+14159989989", "profile_img": "http://s3.amazonaws.com/23e23rf3e3f/h2.jpg", 
	    "social_links":{"facebook": "zuck", "whatsapp": "+14159989989"}, "status":"A short status message."}}
	"""
	if not request.json or not dict_contains_fields(request.json, ["data", "auth_token"]):
		abort(400, "Missing required parameters.")

	auth_token = request.json["auth_token"]
	data = request.json["data"]
	
	user = None
	try:
		user = User.Query.get(user_id=decode_id_from_auth_token(auth_token))
	except:
		abort(400, "User not found")

	if user.auth_token != auth_token:
		abort(401, "Invalid auth token.") # TODO: validate auth token more properly
	
	error = ""

	if "name" in data:
		name = data["name"]
		user.name = name
	if "profile_img" in data:
		profile_img_base64 = data["profile_img"]
		"""
			img_base64_data = re.search("base64,(.*)", profile_img_base64)
			decoded_img = img_base64_data.group(1)

			NUM_SUFFIX_CHARS = 10
			# TODO: better, more cryptic filenames
			img_filename = user.user_id + "-" + binascii.b2a_hex(os.urandom(NUM_SUFFIX_CHARS)) + ".png"

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
			error = "Something went wrong in saving profile image to server.."
			print_error(error)
		"""

	if "status" in data:
		status = data["status"]
		user.status = status
	if "social_links" in data:
		social_links = data["social_links"]
		user.social_links = social_links
	if "email" in data:
		email = data["email"]
		user.email = email
		# TODO: add email verification
	if "phone" in data:
		phone = data["phone"]
		user.phone = phone
		# TODO: add phone verification
	try:
		user.save()
		return jsonify({"errors": error, "user": user_card(user, return_friends=False)}), 200
	except Exception as e:
		error = "Card update could not be saved."
		print_error(error)
		abort(500, error)


@app.route("/favor8/api/v1.0/users/delete", methods=["POST"])
def api_delete_user():
	"""
	  Delete the authenticating user.
	  Resource URL: //favor8/api/v1.0/users/destroy
	  Type: POST
	  Requires Authentication? Yes
	  Parameters:
	   auth_token (required): an active authorization token for this user. String.
	  Example response:
	   {"success": true}
	"""

	if not request.json or not dict_contains_fields(request.json, ["auth_token"]):
		abort(400, "Missing required parameters")

	auth_token = request.json["auth_token"]
	# TODO: validate auth token

	user = None
	try:
		user = User.Query.get(user_id=decode_id_from_auth_token(auth_token))
	except:
		abort(400, "User not found")

	user_id = user.user_id
	# Remove this user from their friends' friend lists
	# TODO: update the Friendships table
	# TODO: error checking. need to run a daemon through users to ensure all friends exist.
	try:
		friends = user.friends 
		for friend in user.friends:
			try:
				user_f = User.Query.get(user_id=friend)
				user_f_friends = user_f.friends
				user_f_friends.remove(user_id)
				user_f.friends = user_f_friends
				user_f.save()
			except:
				pass
	except AttributeError:
		pass
	
	try:
		user.delete()
		return jsonify({"success": True}), 200
	except Exception as e:
		error = "User could not be deleted."
		print_error(error)
		abort(500, error)


@app.route("/favor8/api/v1.0/friends/send_request", methods=["POST"])
def api_send_friend_request():
	"""
	Resource URL: //favor8/api/v1.0/friends/send_request
	Type: POST
	Requires Authentication? Yes
	Parameters
	 target_user_id: user ID of the user who is being added. E.g. g534fb4fu7
	 auth_token: A valid authorization token for the authenticating user. String.
	Example response:
	 {"pending": true}
	"""
	if not request.json or not dict_contains_fields(request.json, ["target_user_id", "auth_token"]):
		abort(400, "Missing parameters.")

	target_user_id = request.json["target_user_id"]
	auth_token = request.json["auth_token"]
	# TODO: validate auth token
	try:
		user1 = User.Query.get(user_id=decode_id_from_auth_token(auth_token))
		user2 = User.Query.get(user_id=target_user_id)
	except Exception as e:
		abort(400, "User not found.")

	outgoing = user1.outgoing_requests
	outgoing.append(user2.user_id)
	user1.outgoing_requests = outgoing

	incoming = user2.incoming_requests
	incoming.append(user1.user_id)
	user2.incoming_requests = incoming

	try:
		user1.save()
		user2.save()
		return jsonify({"pending": True, "user1": user1.user_id, "user2": user2.user_id}), 200
	except:
		abort(500, "Friend request could not be sent")


@app.route("/favor8/api/v1.0/friendships/create", methods=["POST"])
def api_create_friendship():
	"""
	Creates a friendship b/w authenticating user and another user if there is an incoming request.
	Resource URL: //favor8/api/v1.0/friendships/create
	Type: POST
	Requires Authentication? Yes
	Parameters
	 incoming_user_id: user ID of the user who sent a friend request to the authenticating user. E.g. g534fb4fu7
	 auth_token: A valid authorization token for the authenticating user. String.
	Example response:
	{"user_id": 5, "username": "johnny" "name": "Johnny Cash", "phone": "+14159989989", "profile_img": "http://s3.amazonaws.com/23e23rf3e3f/h2.jpg", 
    "accounts":{"facebook": "zuck", "whatsapp": "+14159989989"}, "status":"A short status message."}
	"""
	if not request.json or not dict_contains_fields(request.json, ["incoming_user_id", "auth_token"]):
		abort(400, "Missing parameters.")

	incoming_user_id = request.json["incoming_user_id"]
	auth_token = request.json["auth_token"]
	# TODO: validate auth token

	try:
		user1 = User.Query.get(user_id=decode_id_from_auth_token(auth_token))
		user2 = User.Query.get(user_id=incoming_user_id)
	except Exception as e:
		abort(400, "User not found.")

	try:
		user1_friends = user1.friends
		user1_friends.append(user2.user_id)
		user1.friends = user1_friends
	except:
		user1.friends = [user2.user_id]

	try:
		user1_incoming = user1.incoming_requests
		user1_incoming.remove(user2.user_id)
		user2_outgoing = user2.outgoing_requests
		user2_outgoing.remove(user1.user_id)
	except:
		abort(400, "Friend request has expired.")

	try:
		user2_friends = user2.friends
		user2_friends.append(user1.user_id)
		user2.friends = user2_friends
	except:
		user2.friends = [user1.user_id]

	try:
		user1.save()
		user2.save()
	except Exception as e:
		error = "Something went wrong. User could not be added as a friend."
		print_error(error)
		abort(500, error)
	
	# TODO: send event to user2 and add user 1's card to their stack
	return jsonify(user_card(user2, return_friends=False)), 200


@app.route("/favor8/api/v1.0/friendships/destroy", methods=["POST"])
def api_delete_friendship():
	"""
	Removes a friendship b/w authenticating user and another user. Returns True if removal succeeded, 
	along with an updated list of friends' user IDs.
	Resource URL: //favor8/api/v1.0/friendships/destroy
	Type: POST
	Requires Authentication? Yes
	Parameters
	 target_user_id: user ID of the user who is to be removed from friend list. E.g. 5433
	 auth_token: A valid authorization token for the authenticating user. String.
	Example response:
	{"success": True, "friends": [4, 1233, 44]}
	"""
	if not request.json or not dict_contains_fields(request.json, ["target_user_id", "auth_token"]):
		abort(400, "Missing parameters.")

	target_user_id = request.json["target_user_id"]
	auth_token = request.json["auth_token"]
	# TODO: validate auth token

	try:
		user1 = User.Query.get(user_id=decode_id_from_auth_token(auth_token))
		user2 = User.Query.get(user_id=target_user_id)
	except Exception as e:
		abort(400, "User not found.")

	try:
		user1_friends = user1.friends
		user1_friends.remove(user2.user_id)
		user1.friends = user1_friends

		user2_friends = user2.friends
		user2_friends.remove(user1.user_id)
		user2.friends = user2_friends
	except:
		pass

	try:
		user1.save()
		user2.save()
		# TODO: send event to user2 and add user 1's card to their stack
		return jsonify({"success": True, "friends": friend_list(user1)}), 200
	except Exception as e:
		error = "Something went wrong. User could not be removed from friends."
		print_error(error)
		abort(500, error)


@app.route("/favor8/api/v1.0/friends/list", methods=["GET"])
def api_friends_list():
	"""
	Returns a list of user objects for authenticating user's friends (favorites).
	Resource URL: //favor8/api/v1.0/friends/list
	Type: GET
	Requires Authentication? Yes
	Parameters
	 auth_token: A valid authorization token for the authenticating user. String.
	Example response:
	{"friends": {}, {}, {}}
	"""

	if not request.json or not dict_contains_fields(request.json, ["auth_token"]):
		abort(400, "Missing parameters")

	auth_token = request.json["auth_token"]
	# TODO: validate auth token

	try:
		auth_user = User.Query.get(user_id=decode_id_from_auth_token(auth_token))
	except:
		abort(400, "User not found.")

	user_id = auth_user.user_id
	friend_ids = friend_list(user_id)
	friends = []
	for friend_id in friend_ids:
		try:
			friend = User.Query.get(user_id=friend_id)
			friends.append(user_card(friend, return_friends=False))
		except QueryResourceDoesNotExist:
			pass

	return jsonify({"friends": friends}), 200


@app.route("/favor8/api/v1.0/friends/ids", methods=["GET"])
def api_friends_ids():
	"""
	Get a list of user IDs for authenticating user's friends (favorites).
	Resource URL: //favor8/api/v1.0/friends/ids
	Type: POST
	Requires Authentication? Yes
	Parameters
	 auth_token: A valid authorization token for the authenticating user. String.
	Example response:
	{"friends": [2, 4, 121]}
	"""

	if not request.json or not dict_contains_fields(request.json, ["auth_token"]):
		abort(400, "Missing parameters")

	auth_token = request.json["auth_token"]
	# TODO: validate auth token

	try:
		auth_user = User.Query.get(user_id=decode_id_from_auth_token(auth_token))
	except:
		abort(400, "User not found.")

	user_id = auth_user.user_id
	friend_ids = friend_list(user_id)
	
	return jsonify({"friends": friend_ids}), 200


# Classes
class User(Object):
	pass

class UnverifiedUser(Object):
	pass

class UserCount(Object):
	pass

# Helpers
def friend_list(a_user):
	'''Returns a list of ids of the user's friends'''
	user = User.Query.get(user_id=a_user.user_id)
	try:
		friends = user.friends
		return friends
	except Exception as e:
		return []

def user_card(user, return_friends=True):
	user_card = {}
	protected_fields = ["objectId", "auth_token", "_created_at", "_updated_at", "password"]
	if not return_friends: # so we don't return friends if return_friends=False
		protected_fields.append("friends")
	for field in user.__dict__:
		if field in protected_fields:
			pass
		else:
			user_card[field] = user.__dict__[field]
	return user_card

def dict_contains_fields(dict, fields):
	return all(k in dict for k in fields)

def generate_auth_token(user_id):
	# TODO: Generate better auth tokens
	r = str(random.randint(100000,999999))
	return "%s-abcdefg%s" % (user_id, r)

def decode_id_from_auth_token(auth_token):
	# TODO: update for production-ready auth tokens
	s = ""
	for char in auth_token:
		if char != "-":
			s += char
		else:
			break
	return int(s)

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

	print_debug(sms_body)
	try:
		client = TwilioRestClient(app.config["TWILIO_TEST_ACCOUNT_SID"], app.config["TWILIO_TEST_AUTH_TOKEN"])
		message = client.messages.create(body=sms_body,to=phone_num,from_=app.config["TWILIO_TEST_FROM_NUM"])
		return True

	except twilio.TwilioRestException as e:
		return False

def print_error(error_msg):
	if app.config["DEBUG"] == True:
		print "ERROR: %s" % error_msg

def print_debug(msg):
	if app.config["DEBUG"] == True:
		print msg


if __name__ == "__main__":
	app.run()