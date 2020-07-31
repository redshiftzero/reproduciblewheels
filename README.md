# reproduciblewheels
Monitoring which wheels in the python ecosystem can be reproducibly built

[![CircleCI](https://circleci.com/gh/redshiftzero/reproduciblewheels.svg?style=svg)](https://circleci.com/gh/redshiftzero/reproduciblewheels)

## Developer


Example of regenerating the static site using the existing data:

```
>>> import check
>>> import json
>>> with open('site_data.json', 'r') as f:
...     data = json.loads(f.read())
...
>>> check.regenerate_site(data)
```

or simply both regenerate the data and the static site via:

```
python3 check.py
```
