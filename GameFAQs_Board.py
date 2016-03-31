import logging

logging.basicConfig(level=logging.DEBUG,
                    format=' %(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%d%b%y %I:%M:%S %p')
import requests
import re
from bs4 import BeautifulSoup as bs
from datetime import datetime
from datetime import timedelta

# Supress DEBUG logs from requests library.
logging.getLogger('requests').setLevel(logging.INFO)


class GameFAQSession:
    """ GameFAQs session manager."""

    def __init__(self, login, password, targetuser):
        self.session = requests.Session()
        self.login = login
        self.password = password
        self.userlogin(self.login, self.password)
        self.boardURL = None
        self.targetuser = targetuser
        self.karma = 0
        self.threads = []
        self.targetuser_posts = []
        self.last_time_checked = datetime.now() - timedelta(minutes=15)
        self.gather_targetuser_profile_info()

    def userlogin(self, login, password):
        """ Logs the user into GameFAQs.

        :param login: Email Address for GameFAQs user
        :param password: Password for GameFAQs user
        """

        payload = {
            'PASSWORD': password,
            'path': "http://www.gamefaqs.com/",
            'EMAILADDR': login,
        }

        login_url = 'http://www.gamefaqs.com/user/login'

        # Grab key ID
        resp = self.session.get(login_url)
        soup = bs(resp.text, 'html.parser')
        payload['key'] = soup.find('input', class_='hidden')['value']

        # Login with user payload
        resp = self.session.post(login_url, data=payload)

        soup = bs(resp.text, 'html.parser')

        if soup.find_all(string='There was an error while logging you in: '):
            raise Exception('Login Failed!')
        else:
            logging.debug('{} successfully logged in.'.format(self.login))

    def gather_targetuser_profile_info(self):
        """ Navigates to user's board page and finds all links that are
            more recent than last_time_checked.

            url[0] = url
            url[1] = title
        :rtype: List
        :return: List with url
        """
        targetuser_page = 'http://www.gamefaqs.com/users/' + self.targetuser \
                          + '/boards'

        # Only collect posts that were minutes ago.
        timere = re.compile(r'Posted (\d+) minutes')

        # Get User Leight_Weight page
        resp = self.session.get(targetuser_page)

        # Parse out links and last posted
        soup = bs(resp.text, 'html.parser')
        trs = soup.find('table').find_all('tr')
        self.karma = int(trs[7].get_text()[5:])

        # Create two lists with URL RE - one of full titles and one of URLs
        threads = []
        for tr in trs:
            if tr.find('a'):
                fullurl = 'https://www.gamefaqs.com' + tr.find('a')['href']
                title = tr.find('a').text
                time = timere.search(tr.decode())
                if time:
                    logging.debug("Findlinksuserpage: " + fullurl + " found.")
                    timestamp = datetime.now() - \
                                timedelta(minutes=int(time.groups()[0]))
                    threads.append([fullurl, title,
                                    timestamp.strftime('%m/%d/%y %I:%M%p')])
            else:
                pass

        self.threads = threads

    def find_threads_on_board(self):
        """ Finds threads on the specified board newer than last_time_checked.

        :return: list of list strings -> [URL, thread title, timestamp]
        """

        if self.boardURL is None:
            raise Exception('Must set boardURL attribute first.')

        # Get first page of the board.
        resp = self.session.get(self.boardURL)
        soup = bs(resp.text, 'html.parser')
        threads_in_board = soup.find_all("td", class_='lastpost')
        num_pages = self.find_num_pages(resp.text)

        thread_info = self.threads
        for page in range(num_pages):
            if page > 0:
                resp = self.session.get(self.boardURL + "?page={}".format(page))
                soup = bs(resp.text, 'html.parser')
                threads_in_board = soup.find_all("td", class_='lastpost')

            threadcounter = 0
            for thread in threads_in_board:
                # If thread time is more recent than the last time
                # board was checked, include URL.
                timestamp = datetime.strptime(thread.string.replace(' ', '/16 '), '%m/%d/%y %I:%M%p')
                if self.last_time_checked < timestamp:
                    zoomin = thread.parent.find('td', class_='topic')
                    logging.debug('find_new_threads: Thread found - '
                                  + zoomin.a.string)
                    logging.debug('find_new_threads: Thread time - ' +
                                  thread.string.replace(' ', '/16 '))
                    title = zoomin.a.string
                    logging.debug('find_new_threads: ' +
                                  'URL -  http://www.gamefaqs.com/' +
                                  zoomin.a['href'])
                    threadcounter += 1
                    thread_info.append(['http://www.gamefaqs.com/' +
                                        zoomin.a['href'], title,
                                        timestamp.strftime('%m/%d/%y %I:%M%p')])

            # Do not go to next page of board
            # unless all threads were newer than last_time_checked
            if len(threads_in_board) != threadcounter:
                break

        logging.info('{} threads found.'.format(len(thread_info)))
        self.threads = thread_info

    def find_num_pages(self, html_text):
        """ Returns the number of pages

        :param html_text, html response text
        :return: integer, max number of pages
        """
        soup = bs(html_text, 'html.parser')
        pages = soup.find_all('ul', class_='paginate')
        # Default to 1 page post
        page_max = 1
        for page in pages:
            if page["class"] == ["paginate"]:
                page_max = int(re.compile(r'of (\d+)')
                               .search(page.get_text()).groups()[0])
                break

        return page_max

    def find_posts_by_targetuser(self):
        """ Finds user posts on URL by username newer than last_time_checked

        :return: list of list strings -> [URL, thread title, post text, timestamp]
        """

        if not self.threads:
            raise Exception('No threads present in class. ' +
                            'Run find_threads_on_board first.')

        title_strip_text = ' - Current Events Message Board - GameFAQs'
        post_bodies = []
        page_counter = 0
        total_pages = len(self.threads)
        for thread in self.threads:
            thread_url = thread[0]
            resp = self.session.get(thread_url)
            thread_pages = self.find_num_pages(resp.text)
            total_pages += thread_pages - 1
            soup = bs(resp.text, 'html.parser')
            postbody = ''

            for page in range(thread_pages):
                page_counter += 1
                logging.debug('Loading page {} of {}'
                              .format(page_counter, total_pages))
                if page > 0:
                    thread_url = thread[0] + '?page={}'.format(page)
                    resp = self.session.get(thread_url)
                    soup = bs(resp.text, 'html.parser')
                # If target user exists anywhere in page.
                if soup.find_all(string=self.targetuser):
                    # Find all posts created by target user.
                    for post in soup.find_all(string=self.targetuser):
                        for parent in post.parents:
                            if parent.name == "td" and parent['class'][0] == 'msg':
                                # Find post time, replace &nsbp with
                                # a normal space.
                                post_time_str = parent.find('span', class_='post_time')['title']\
                                                            .replace(u'\xa0', ' ')
                                # Convert string time to datetime.
                                post_time_dt = datetime.strptime(post_time_str, '%m/%d/%Y %I:%M:%S %p')
                                # If post is newer than last time checked.
                                # if True: # <-- Used for debugging.
                                if self.last_time_checked < post_time_dt:
                                    logging.info('Post Found! Time - ' + post_time_str)
                                    title = soup.title.string\
                                                .replace(title_strip_text, '')

                                    # Remove user_subnav from parent.parent
                                    parent.parent.find('ul').decompose()
                                    post_body = str(parent.parent)
                                    post_bodies.append([post_body,
                                                        thread_url,
                                                        title,
                                                        post_time_str])
                                    break
                                else:
                                    logging.debug("Post not more recent than last_time_checked.")
                else:
                    logging.debug("Username not found.")

        logging.info('{} pages checked, {} found containing {}.'
                     .format(page_counter, len(post_bodies), self.targetuser))
        self.targetuser_posts = post_bodies

