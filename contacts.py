from flask import Flask, render_template, request, json

from parse_rest.datatypes import Object
from parse_rest.query import QueryResourceDoesNotExist
from parse_rest.connection import register

app = Flask(__name__)
app.config.from_object("config")

app.config["DEBUG"] = True

register(app.config["PARSE_APP_ID"], app.config["PARSE_RESTAPI_KEY"])

@app.route("/")
def index():
	return "API v1"


""" 
  * Resource URL: https://favor8api.heroku.com/account/register
  * Type: POST
  * Requires Authentication? No
  * Response formats: JSON
  * Parameters
   * name (required): The full name of the user
   * user_key (required): A unique identification key, such as email address or phone number.
  * Example request: 
   * POST http://favor8api.heroku.com/account/register?name=Siddharth%20Jha&user_key=9812345678
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
			import pdb; pdb.set_trace()
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


# Stubs
@app.route("/cards/update", methods=["POST"])
def update_card():
	if request.method == "POST":
		user = None
		if "user_object_id" in request.form:
			try:
				user = User.query.get(objectId=request.form["user_object_id"])
			except Exception as e:
				return user_does_not_exist()

			try:
				# TODO: validation for the fields
				if "name" in request.form:
					user.name = request.form["name"]
				if "profile_img" in request.form:
					user.profile_img = request.form["profile_img"]
				if "account_list" in request.form:
					user.account_list = request.form["account_list"]
				if "user_key" in request.form:
					user.user_key = request.form["user_key"]
				if "status" in request.form:
					user.status = request.form["status"]

				user.save()
				return json.dumps({"successMsg": "User successfully updated"}), 200
			except Exception as e:
				error = "ERROR: Profile could not be updated"
				print_error(error)
				return json.dumps({"error": error}), 500
		else:
			error = "ERROR: User id missing"
			print_error(error)
			return json.dumps({"error": error}), 400
	else:
		return only_post_supported()


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