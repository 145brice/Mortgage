import urllib.request, json, pprint

url = 'http://localhost:5000/api/data'
try:
    data = urllib.request.urlopen(url, timeout=10).read()
    j = json.loads(data)
    rows = j.get('rows', [])
    print('Rows:', len(rows))
    pprint.pprint(rows[:10])
    print('\nStats:', j.get('stats'))
except Exception as e:
    print('Error fetching API:', e)
