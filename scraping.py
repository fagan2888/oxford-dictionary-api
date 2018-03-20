#!/bin/env python

""" scraping oxford info with a word list """

import json
import logging
import os
import time
import urllib.request

from exceptions import ConnectionError, HTTPError, Timeout
from oxford import Word

# disable requests logging
logging.getLogger("requests").setLevel(logging.CRITICAL)

AUDIO_PATH = os.path.join(os.path.expanduser('~'), 'Github/VE-Dictionary/data/audio')
DEF_PATH = os.path.join(os.path.expanduser('~'), 'Github/VE-Dictionary/data/words')


def mkdir(path):
	""" create directory if not exists """
	if not os.path.isdir(path):
		os.makedirs(path)

def touch(path, content=''):
	""" create new file like a boss """
	dirname = os.path.dirname(path)
	mkdir(dirname)
	with open(path, 'w') as file:
		file.write(content)

def settup_logger(name, logfile, level=logging.INFO):
	""" setup logger. Usage:

	LOG = settup_logger('info', 'scraping.log', level=logging.INFO)

	LOG.info('info message')
	LOG.debug('debug message')
	"""
	formatter = logging.Formatter(
			'[%(asctime)s] %(lineno)-3d %(filename)-10s %(levelname)-8s %(message)s')

	handler = logging.FileHandler(logfile)
	handler.setFormatter(formatter)

	logger = logging.getLogger(name)
	logger.setLevel(level)
	logger.addHandler(handler)

	return logger


# pylint: disable=invalid-name
LOG_PATH = os.path.join(os.getcwd(), 'cache', 'scraping.log')
if not os.path.isfile(LOG_PATH):
	touch(LOG_PATH)
LOG = settup_logger('info', LOG_PATH, level=logging.INFO)

def timer(function):
	""" decorator to time function call
	@timer
	def test():
		for _ in range(0, 10000):
			pass

	test()
	test.elapsed
	"""
	def time_function_call(*args, **kwargs):
		""" get time of function call """
		start = time.time()
		function_result = function(*args, **kwargs)
		end = time.time()
		time_function_call.elapsed = end - start

		return function_result

	return time_function_call

def download(url, directory):
	""" download url to directory
	Argument: (https://abc/innocent_file.exe, C:\Program Files\system32\)
	Download file to C:\Program Files\system32\innocent_file.exe
	"""
	path = os.path.join(directory, url.split('/')[-1])
	urllib.request.urlretrieve(url, path)

def save(word, path):
	""" write word data in json format with filename is word value """
	if word is not None:
		filename = word['word']
		cache_path = os.path.join(path, filename + '.json')
		touch(cache_path)

		with open(cache_path, 'w') as file:
			json.dump(word, file)

def put(line, filename):
	""" append a line to a file """
	if not os.path.isfile(filename):
		touch(filename)

	with open(filename, 'a') as file:
		file.write(line + '\n')

def update_skipped_words(word):
	""" update words that has to be skipped (connection error) to a file """
	path = os.path.join(os.getcwd(), 'cache', 'skipped_words.txt')
	put(word, path)

def update_not_found_words(word):
	""" update not found words (in oxford diciontary) """
	path = os.path.join(os.getcwd(), 'cache', 'not_found_words.txt')
	put(word, path)

def update_corrupted_words(word):
	""" update words that has corrupted data for some reasons """
	path = os.path.join(os.getcwd(), 'cache', 'corrupted_words.txt')
	put(word, path)

def read(filename):
	""" read content from a file
	return: a dictionary of key-value where key is content in a line in string
	and value is None
	"""
	if not os.path.isfile(filename):
		touch(filename)

	with open(filename, 'r') as file:
		words = file.readlines()

	return {word.strip(): None for word in words}

def get_not_found_words():
	""" update not found words (in oxford diciontary) """
	path = os.path.join(os.getcwd(), 'cache', 'not_found_words.txt')
	return read(path)

def get_downloaded_words():
	""" get list of words whose data have been downloaded before """
	return {file.strip('.json').lower(): None
			for file in os.listdir(DEF_PATH) if os.path.isfile(os.path.join(DEF_PATH, file))}

def get_wordlist(filename):
	""" get wordlist in current working directory """
	path = os.path.join(os.getcwd(), filename)
	return read(path)

DOWNLOADED_WORDS = get_downloaded_words()
NOT_FOUND_WORDS = get_not_found_words()

@timer
def extract_data(word):
	""" get word info and store in filesystem

	argument: word to extract data
	return (statuscode, references)

	status code: 0 on success, 1 on error
	references: a list of other keywords (same word with different wordform)
	"""
	try:
		print("Request html page of '{}'...".format(word))
		LOG.info("Request html page of '%s'...", word)

		Word.get(word)
	except (ConnectionError, HTTPError, Timeout) as error:
		print("Requests failed: '{}'".format(error))
		LOG.debug("Requests failed: '%s'", error)

		update_skipped_words(word)
		return (1, None)

	try:
		print("Extracting data from '{}'...".format(word))
		LOG.info("Extracting data from '%s'...", word)

		word_data = Word.info()

		if word_data is None:
			print("No data for '{}' word. Skipping".format(word))
			LOG.info("No data for '%s' word. Skipping", word)

			update_not_found_words(word)
			return (1, None)

		# download pronounce audio file
		print("Getting audio file urls of '{}'...".format(word))
		LOG.info("Getting audio file urls of '%s'...", word)

		br_audio = word_data['pronunciations']['britain']['url']
		am_audio = word_data['pronunciations']['america']['url']

		print("Downloading audio file of '{}'...".format(word))
		LOG.info("Downloading audio file of '%s'...", word)

		download(br_audio, AUDIO_PATH)
		download(am_audio, AUDIO_PATH)

		# save word information (definitions, examples, idioms,...)
		print("saving '{}' in json format to {}...".format(word, DEF_PATH))
		LOG.info("saving '%s' in json format to %s...", word, DEF_PATH)

		save(word_data, DEF_PATH)

	except Exception as error:
		print("something failed: '{}'".format(error))
		LOG.debug("something failed: '%s'", error)

		update_corrupted_words(word)
	else:
		return (0, word_data['other_keyword'])

def scrap(words, reference=True):
	""" scrap list of words
	reference (bool): scrap other wordform of a word
	"""
	for word in words:
		print("scraping '{}'...".format(word))

		if word in DOWNLOADED_WORDS:
			print("'{}' has been downloaded. Skipping to next word".format(word))
			continue
		elif word in NOT_FOUND_WORDS:
			print("'{}' not found. Skipping to next word".format(word))
			continue
		else: # valid word. Downloading...
			exitcode, others = extract_data(word)

		if exitcode == 1: # Word not found. Skip to next word immediately
			continue
		elif exitcode == 2: # Connection error
			time.sleep(10)
		else: # success
			print("scrap reference words: '{}'".format(others))
			if others and reference is True:
				scrap(others, reference=False)

		print('cooldown...') # cooldown time: 4s
		if extract_data.elapsed < 4:
			time.sleep(4 - extract_data.elapsed)

def run(filename):
	""" scrap words from a wordlist in filename """
	print('getting wordlist data from {}'.format(os.path.join(os.getcwd(), filename)))
	words = get_wordlist(filename)
	scrap(words, reference=True)

# vim: nofoldenable