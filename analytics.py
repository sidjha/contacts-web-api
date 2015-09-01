from postmark import PMMail
from config import POSTMARK_API_TOKEN

def new_user_signed_up(user):
	'''When a new user signs up'''
	u = extract_basic_info(user)
	text_body = "%s (user id: %s) signed up via %s method. Full name: %s" % (u["username"], u["user_id"], u["via"], u["real_name"])
	try:
		subject = "Favor8 Analytics: New User signed up: %s" % u["username"]
		sendmail(subject, text_body)
		return True
	except:
		print "Analytics Error: New user event couldn't be emailed"
		return False

def user_logged_in(user):
	'''When a user logs in'''
	import pdb; pdb.set_trace()
	u = extract_basic_info(user)
	text_body = "%s (user id: %s) logged-in via %s method. Full name: %s" % (u["username"], u["user_id"], u["via"], u["real_name"])
	try:
		subject = "Favor8 Analytics: User logged in: %s" % u["username"]
		return send_mail(subject, text_body)
		return True
	except:
		print "Analytics Error: User log-in event couldn't be emailed"
		return False


def send_mail(subject, text_body, tag="favor8"):
	''' Send an email with analytics event '''
	message = PMMail(api_key = POSTMARK_API_TOKEN,
	                 subject = subject,
	                 sender = "sid@mesh8.co",
	                 to = "sid@mesh8.co",
	                 text_body = text_body,
	                 tag = tag)

	message.send()

def extract_basic_info(user):
	u = {}
	u["username"] = "" if "username" not in user else user["username"]
	u["via"] = "" if "via" not in user else user["via"]
	u["real_name"] = "" if "name" not in user else user["name"]
	u["user_id"] = "" if "user_id" not in user else str(user["user_id"])
	return u