import logging

logging.basicConfig(filename='spider_log.log',
                    level=logging.INFO,
                    format=' %(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%d%b%y %I:%M:%S %p')

from GameFAQs_Board import GameFAQSession
from datetime import datetime
from datetime import timedelta
import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import sys
import getopt


def readjson():
    """ Initializes variables used by the bot.

    :return: Returns a dictionary of bot variables (Keys: karmavar, time)
    """
    try:
        f = open('botvars.json', 'r')
        variables = json.loads(f.read())
    except FileNotFoundError as e:
        # If file not found, create initial values.
        logging.debug(str(e) + '. Creating botvars.json')
        variables = {'karmavar': 0,
                     'time': (datetime.now() - timedelta(minutes=15)).strftime('%m/%d/%y %I:%M%p')}
        f = open('botvars.json', 'w')
        f.write(json.dumps(variables))
        f.close()
    return variables['karmavar'], variables['time']


def updatejson(karma):
    f = open('botvars.json', 'w')
    variables = {'karmavar': karma,
                 'time': datetime.now().strftime('%m/%d/%y %I:%M%p')}
    f.write(json.dumps(variables))
    f.close()
    logging.debug('Main: JSON updated with karma and current time.')


def send_email(emails, html, smtpserver='smtp.gmail.com:587'):
    """
        Sends email with body of html to list of email users
    :param emails: List of email addresses
    :param html: HTML text for attaching to email
    :param smtpserver:
    :return:
    """

    sender = 'pythonnotify2@gmail.com'

    msg = MIMEMultipart('alternative')
    msg['Subject'] = "GameFAQs Spider"
    msg['From'] = sender
    msg['To'] = ','.join(emails)

    htmlbody = MIMEText(html, 'html')
    msg.attach(htmlbody)

    server = smtplib.SMTP(smtpserver)
    server.starttls()
    server.login(sender, 'yV7RhxZGv5D9tDmj')
    server.sendmail(sender, emails, msg.as_string())
    server.quit()


def format_html(userposts):
    """ Takes a list of HTML blocks and inserts them into the body of an
        email with title, time, and url above the body of the text.

    :param userposts: List of html blocks
            html_in[0] - HTML for post
            html_in[1] - Thread URL
            html_in[2] - Post title
            html_in[3] - Post time string
    :return: Properly formatted HTML for attaching to email body.
    """

    posts_to_insert = ''
    for content in userposts:
        html_post = content[0]
        thread_url = content[1]
        title = content[2]
        post_time = content[3]
        base = """<h2><a href="{0}">{1}</a></h2>
                    <h3>{2}</h3>{3}"""\
                .format(thread_url, title, post_time, html_post)
        posts_to_insert += base
    htmlbody = """\
    <html>
      <head></head>
      <body>
        {}
      </body>
    </html>
    """.format(posts_to_insert)
    return htmlbody


def main(argv):

    # Mark start of script
    start_time = datetime.now()

    username = ''
    password = ''
    target = ''
    email_to_notify = []
    try:
        opts, args = getopt.getopt(argv, 'hu:p:t:e:', ['username=', 'password=', 'target=', 'email='])
    except getopt.GetoptError:
        print('main_spider.py -u <username> -p <password> -t <target> -e <email>\n \
              May append multiple emails, each proceeded by the -e flag.')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('main_spider.py -u <username> -p <password> -t <target> -e <email>\n \
              May append multiple emails, each proceeded by the -e flag.')
            sys.exit()
        elif opt in ("-u", "--username"):
            username = arg
        elif opt in ("-p", "--password"):
            password = arg
        elif opt in ("-t", "--target"):
            target = arg
        elif opt in ("-e", "--email"):
            email_to_notify.append(arg)

    # Load saved variables from previous run.
    last_karma, last_checked = readjson()

    session = GameFAQSession(username, password, target)

    # Set last checked time in session.
    session.last_time_checked = datetime.strptime(last_checked, '%m/%d/%y %I:%M%p')

    # Set board to parse.
    session.boardURL = 'http://www.gamefaqs.com/boards/400-current-events'

    # Get new threads.
    session.find_threads_on_board()

    # Find posts by target user on found threads.
    session.find_posts_by_targetuser()

    # Write karma & time to json file.
    updatejson(session.karma)

    logging.info("Script execution time: " + str(datetime.now() - start_time))

    karma_increase = session.karma > last_karma

    if session.targetuser_posts or karma_increase:

        # Using posts, create an emailbody for sending through sendemail()
        # [post body, URL, thread title, timestamp]
        emailbody = ''

        if karma_increase:
            emailbody = '{} karma increased from {} to {}'\
                        .format(session.targetuser, last_karma, session.karma)

        logging.debug('Adding posts to email body.')
        emailbody += format_html(session.targetuser_posts)

        # send_email(['jeffrey.slabaugh+python@gmail.com',
        #             'laneslabaugh+python@gmail.com'], emailbody)
        send_email(email_to_notify, emailbody)
        logging.info('Email generated & sent!')

if __name__ == "__main__":
    main(sys.argv[1:])
