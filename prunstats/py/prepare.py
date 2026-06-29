from __future__ import annotations

import collections
import dataclasses
import csv
import json
import sys
import typing

def main() -> None:
	(month,) = sys.argv[1:]

	with open(f'rawData/{month}.csv', 'r', newline='') as f:
		data = read_data(f)

	bases_data: dict[str, dict[str, int]] = {r.company_id: {'bases': r.num, 'rank': r.rank} for r in data['BASES']}
	with open(f'www/data/base-data-{month}.json', 'w') as f:
		json.dump(bases_data, f)
	ships_data: dict[str, dict[str, int]] = {r.company_id: {'ships': r.num, 'rank': r.rank} for r in data['SHIPS']}
	with open(f'www/data/ship-data-{month}.json', 'w') as f:
		json.dump(ships_data, f)

	with open(f'rawData/{month}-prices.json', 'r') as f:
		prices = get_prices(f)

	prod_data, company_data = get_prod_and_company_data(data, prices)
	with open(f'www/data/prod-data-{month}.json', 'w') as f:
		json.dump(prod_data, f)
	with open(f'www/data/company-data-{month}.json', 'w') as f:
		json.dump(company_data, f)

def read_data(f: typing.TextIO) -> dict[str, list[Row]]:
	data: dict[str, list[Row]] = collections.defaultdict(list)
	reader = csv.reader(f)
	for row in reader:
		data[row[0]].append(Row(int(row[1]), int(row[2]), row[3]))
	return data

def get_prices(f: typing.TextIO) -> typing.Mapping[str, float]:
	raw_prices: typing.Sequence[Price] = json.load(f)
	volumes: dict[str, float] = collections.defaultdict(float)
	traded: dict[str, int] = collections.defaultdict(int)
	for price in raw_prices:
		if price['Traded30D'] is None:
			continue
		assert price['VWAP30D'] is not None
		volumes[price['MaterialTicker']] += price['VWAP30D'] * price['Traded30D']
		traded[price['MaterialTicker']] += price['Traded30D']

	prices = {ticker: volume / traded[ticker] for ticker, volume in volumes.items()}

	hardcoded_prices = {
		'AFP': 116868,
		'ANZ': 70601,
		'BFP': 23408,
		'BND': 230,
		'BID': 47011,
		'CRU': 169623,
		'CQT': 378452,
		'FUN': 124010,
		'GCH': 18303,
		'GNZ': 30361,
		'HNZ': 93580,
		'PFG': 2677222,
		'PK': 869,
		'RDS': 598170,
		'SDM': 1721027,
		'SST': 5863587,
		'SU': 157860,
		'TOR': 540169,
		'VCB': 673713,
		'WOR': 202000,
	}
	assert frozenset(prices).isdisjoint(hardcoded_prices)
	prices.update(hardcoded_prices)
	return prices

def get_prod_and_company_data(data: dict[str, list[Row]], prices: typing.Mapping[str, float]
		) -> tuple[typing.Mapping[str, ProdData], typing.Mapping[str, typing.Any]]:
	prod: dict[str, ProdData] = {}
	individual: dict[str, dict[str, CompanyTickerData]] = collections.defaultdict(dict)
	totals: dict[str, CompanyTotals] = collections.defaultdict(lambda: {'volume': 0.0})

	for section, rows in data.items():
		if (ticker := get_production_ticker(section)) is None:
			continue
		price = prices.get(ticker)
		if price is None:
			continue
		prod_amount = sum(row.num for row in rows) / 30
		prod[ticker] = {'amount': prod_amount, 'volume': prod_amount * price}
		for row in rows:
			amount = row.num / 30
			volume = amount * price
			individual[row.company_id][ticker] = {
				'amount': amount,
				'volume': volume,
				'rank': row.rank,
			}
			totals[row.company_id]['volume'] += volume

	company_data = {'totals': add_company_ranks(totals), 'individual': dict(individual)}
	return prod, company_data

def get_production_ticker(section: str) -> str | None:
	prefix = 'PRODUCTION_'
	suffix = '_DAYS_30'
	if not section.startswith(prefix) or not section.endswith(suffix):
		return None
	return section[len(prefix):-len(suffix)]

def add_company_ranks(totals: dict[str, CompanyTotals]) -> dict[str, CompanyTotals]:
	ranked = sorted(totals.items(), key=lambda item: item[1]['volume'], reverse=True)
	for rank, (company_id, company_totals) in enumerate(ranked, start=1):
		company_totals['volumeRank'] = rank
	return totals

@dataclasses.dataclass(frozen=True, slots=True, eq=False)
class Row:
	rank: int
	num: int
	company_id: str

class Price(typing.TypedDict):
	MaterialTicker: str
	VWAP30D: float | None
	Traded30D: int | None

class ProdData(typing.TypedDict):
	amount: float
	volume: float

class CompanyTickerData(typing.TypedDict):
	amount: float
	volume: float
	rank: int

class CompanyTotals(typing.TypedDict, total=False):
	volume: float
	volumeRank: int

if __name__ == '__main__':
	main()
