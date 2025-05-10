import os, sys, time, pytz, yaml, requests, json
import pandas as pd
from datetime import datetime, timedelta
from copy import deepcopy

beijing_timezone = pytz.timezone('Asia/Shanghai')
current_date_time = datetime.now(beijing_timezone)
year = current_date_time.strftime("%Y")
current_date = current_date_time.strftime("%Y-%m-%d")
one_week_ago_date_time = current_date_time - timedelta(days=7)
one_week_ago_date = one_week_ago_date_time.strftime("%Y-%m-%d")
_time=f'{one_week_ago_date}T00:00:00.000Z'

def if_valid(info: dict, term: str) -> list | None:
    categories: list = [category['name'] for category in info['categories']]
    if not term in categories:
        return None
    else:
        return categories

def get_SI(SI_info: list) -> list:
    item = []
    for SI in SI_info:
        item.append({'title': SI['title'], 'assetLink': SI['asset']['original']['url']})
    return item

def extract_info(info: dict, term: str) -> dict:
    item = {}
    if if_valid(info, term):
        item['doi'] = info['doi']
        item['title'] = info['title']
        item['abstract'] = info['abstract']
        item['categories'] = '; '.join(if_valid(info, term))
        item['publishedDate'] = info['publishedDate']
        item['suppItems'] = get_SI(info['suppItems'])
        item['assetLink'] = info['asset']['original']['url']
    return item

def generate_table(items: list[dict[str, str]], ignore_keys: list=[]) -> str:
    items = deepcopy(items)
    formatted_papers:  list[dict[str, str]] = []
    keys = items[0].keys()
    for paper in items:
        # process fixed columns
        formatted_paper = {}
        ## Title and Link
        formatted_paper['Title'] = f'**[{paper['title']}]({paper['assetLink']})**'
        ## Process Date (format: 2021-08-01T00:00:00Z -> 2021-08-01)
        formatted_paper['Date'] = paper['publishedDate'].split('T')[0]
        
        # process other columns
        for key in keys:
            if key in ['title', 'publishedDate'] or key in ignore_keys:
                continue
            elif key == 'abstract':
                # add show/hide button for abstract
                formatted_paper[key.capitalize()] = f'<details><summary>Show</summary><p>{paper[key]}</p></details>'
            elif key == 'suppItems':
                formatted_paper[key.capitalize()] = f'<details><summary>Show</summary><p>{json.dumps(paper[key])}</p></details>'
            else:
                formatted_paper[key.capitalize()] = paper[key]
        formatted_papers.append(formatted_paper)

    # generate header
    columns = formatted_papers[0].keys()
    # highlight headers
    columns = ['**' + column + '**' for column in columns]
    header = f'| {' | '.join(columns)} |'
    header = f'{header}\n| {' | '.join(['---'] * len(columns))} |'
    # generate the body
    body = ''
    for paper in formatted_papers:
        body += f'\n| {' | '.join(paper.values())} |'
    return header + body


if __name__ == '__main__':
    with open('config.yml', 'r', encoding='utf-8') as cy:
        config: dict = yaml.full_load(cy)

    items = []
    for term in config['terms']:
        url=f'https://chemrxiv.org/engage/chemrxiv/public-api/v1/items?term="{term}"&limit=50&searchDateFrom={_time}&sort=PUBLISHED_DATE_DESC'
        response = requests.get(url)

        try:
            assert response.status_code == 200
            content = response.json()
            for item in content['itemHits']:
                info: dict = item['item']
                if extract_info(info, term):
                    items.append(extract_info(info, term))
            time.sleep(5)
        except Exception as e:
            print(e)

    if items:
        limit = config['limit']
        issue_limit = config['issue_limit']

        df = pd.DataFrame(items).drop_duplicates(subset=['doi'])[:limit]
        ignore_keys = [x for x in df.columns if not x in config['md_keys']]
        os.makedirs(f'Papers/{year}', exist_ok=True)
        df.to_csv(f'Papers/{year}/{current_date_time.strftime("%Y-%m-%d")}.csv', index=False)
        items = [items[x] for x in df.index]

        with open('README.md', 'w') as f_rm:
            f_rm.write('# Weekly Papers\n')
            f_rm.write(
                f'This project automatically fetches the latest papers from ChemRxiv based on categories.\n\n'
                f'Only the most recent articles for each category are retained, up to a maximum of 100 papers.\n\n'
                f'You can click the "Watch" button to receive daily email notifications.\n\n'
                f'Last update: {current_date}\n\n'
                )
            rm_table = generate_table(items, ignore_keys=ignore_keys)
            f_rm.write(f'{rm_table}\n\n')

        with open('.github/ISSUE_TEMPLATE.md', 'w') as f_is:
            f_is.write('---\n')
            f_is.write(f'title: Latest {min(issue_limit, len(df))} Papers - {current_date_time.strftime("%B %d, %Y")}\n')
            f_is.write('labels: documentation\n')
            f_is.write('---\n')
            f_is.write('**Please check the [Github](https://github.com/hdj020402/chemrxiv-daily) page for more papers.**\n\n')
            is_table = generate_table(items[:issue_limit], ignore_keys=ignore_keys + ['abstract', 'doi', 'categories', 'suppItems', 'assetLink'])
            f_is.write(f'{is_table}\n\n')

    else:
        sys.exit('Failed to fetch papers.')



