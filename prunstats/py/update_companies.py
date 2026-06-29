from __future__ import annotations
import time

import json
import tomllib
import typing

import httpx

def main() -> None:
	with open('config.toml', 'rb') as f:
		config = tomllib.load(f)
	fio_api_key = config['fio_api_key']

	with open('www/data/knownCompanies.json', 'r') as f:
		companies = json.load(f)

	now = int(time.time())
	cached: set[str] = set()
	for co in companies.values():
		co_last_update = co.get('LastUpdated')
		if co_last_update is not None and now - co_last_update < 24 * 60 * 60:
			cached.add(co['Username'].casefold())
	print(len(cached), 'cached companies')

	all_users: typing.Collection[str] = httpx.get('https://rest.fnar.net/user/allusers',
			headers={'Authorization': fio_api_key}).raise_for_status().json()

	try:
		for username in all_users:
			if username.casefold() in cached:
				continue

			response = get_with_retry('https://rest.fnar.net/user/' + username)
			if response.status_code in (204, 404):
				print(username, 'not found')
				continue
			fio_user = response.json()
			assert username.casefold() == fio_user['UserName'].casefold(), f'{username} != {fio_user["UserName"]}'
			known_user = {'Username': username, 'LastUpdated': now}
			if corp := fio_user.get('CorporationCode'):
				known_user['Corporation'] = corp
			if known_user == companies.get(fio_user['CompanyId']):
				print(username, 'had no change')
			else:
				print(known_user)
				companies[fio_user['CompanyId']] = known_user
	finally:
		with open('www/data/knownCompanies.json', 'w') as f:
			json.dump(companies, f)

def get_with_retry(url) -> httpx.Response:
	for attempt in range(10):
		try:
			response = httpx.get(url)
		except httpx.TransportError as e:
			print(e, 'retrying in', attempt)
			time.sleep(attempt)
			continue
		if response.status_code in (204, 404) or response.is_success:
			return response
		elif attempt == 9:
			response.raise_for_status()
		print(response.status_code, 'retrying in', attempt)
		time.sleep(attempt)
	raise AssertionError

if __name__ == '__main__':
	main()
