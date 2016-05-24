import configparser
import logging
import json
import datetime


import evelink


from flask import Flask, render_template, request, redirect, url_for
from flask.ext.cache import Cache


from libs.utils import Utils, format_currency
from libs.pi_utils import PiUtils
from libs.losses_utils import LossesUtils
from libs.alliance_utils import AllianceUtils

with open('config.json') as c:
    config = json.load(c)


eve = evelink.eve.EVE()


app = Flask(__name__)
app.config.update(config)


utils     = Utils(app.config)
pi        = PiUtils(app.config, utils)
losses    = LossesUtils(app.config)
alliances = AllianceUtils(app.config)
cache     = Cache(app, app.config)
logging.basicConfig(filename='%s/log' % (config['general']['base_dir']), level=logging.DEBUG)

@cache.memoize()
def character_name_from_id(id_):
    return eve.character_name_from_id(id_)[0]


app.jinja_env.filters['format_currency'] = format_currency
app.jinja_env.filters['character_name_from_id'] = character_name_from_id
app.jinja_env.filters['alliance_id_from_corp_id'] = alliances.alliance_id_from_corp_id
app.jinja_env.filters['alliance_name_from_id']    = alliances.alliance_name_from_id

def error(info):
    return render_template('error.html', info=info)


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html', name=config['project_name'])

@app.route('/stats/pi', methods=['GET'])
def stats_pi():
    
    if 'tier' not in request.args:
        return redirect(url_for('stats_pi', tier=3))

    tier = request.args['tier']

    results = {}

    systems = config['statistics']['pi_systems']

    for system_name in systems:
        system = utils.lookup_system(system_name)
        data   = pi.get_prices(tier, system.solarSystemID)

        if data:
            results[system.solarSystemName.lower()] = {'data':data, 'cached_time':data[0].date}

    return render_template('stats/pi.html', results=results, name=config['project_name'])

@app.route('/stats/ship_details')
def stats_ships_details():
    days = 20
    character_id = None
    filter_options = ['used','lost']

    if 'days' in request.args:
        try:
            days = int(request.args.get('days'))
        except:
            return error('incorrect days')


    if 'ship' in request.args:
        ship_name = request.args.get('ship')
        ship_id   = utils.lookup_typeid(ship_name)

        if not ship_id:
            return error('ship not found')


    if 'character' in request.args:
        character = request.args.get('character')

        if character != 'all':
            try:
                character_id = int(request.args.get('character'))
            except:
                return error('unable to find character')


    filter_option = request.args.get('filter_option')
    coalition   = request.args.get('coalition')

    if filter_option not in filter_options:
        filter_option = 'used'

    if 'coalition' not in request.args:
        coalition = list(config['coalitions'].keys())[0]

    # If the coalition exists in the config, grab the alliance ids for it
    if coalition in config['coalitions']:
        alliance_ids = config['coalitions'][coalition]

    else:
        return error('incorrect coalition')

    current_time = datetime.datetime.utcnow()
    days_ago     = current_time - datetime.timedelta(days=days)
    
    # HOW THE FUCK DOES THIS WORK??
    query = losses.query(alliance_ids, characterID=character_id, shipTypeID=ship_id, days_ago=days_ago, kills=filter_option)



    return render_template('stats/ships_details.html', 
                            coalition=coalition, 
                            data=query, 
                            ship_name=ship_name, 
                            ship_id=ship_id, 
                            filter_option=filter_option,
                            name=config['project_name'])



@app.route('/stats/ships', methods=['GET'])
def stats_ships():
    current_time = datetime.datetime.utcnow()
    days         = 20
    character_id = None
    character    = None
    total_ships_lost = 0
    ships_lost = {}
    ship_id      = 0
    filter_options = ['used','lost']

    if 'days' in request.args:
        try:
            days = int(request.args.get('days'))
        except:
            return error('are you sure thats a number?')


    if 'ship' in request.args:
        ship_name = request.args.get('ship')
        ship_id   = utils.lookup_typeid(ship_name)

        if not ship_id:
            return error('ship not found')


    
    if 'character' in request.args:
        character = request.args.get('character')
        if character != 'all':
            try:
                character_id = int(request.args.get('character'))
            except:
                return error('unable to find character')


    filter_option = request.args.get('filter_option')
    coalition     = request.args.get('coalition')
    days_ago      = current_time - datetime.timedelta(days=days)

    if filter_option not in filter_options:
        filter_option = 'used'


    if 'coalition' not in request.args:
        coalition = list(config['coalitions'].keys())[0]

    if coalition in config['coalitions']:
        alliance_ids = config['coalitions'][coalition]

    else:
        return error('incorrect coalition')


    if character_id:
        query = losses.query_total(alliance_ids, days_ago=days_ago, characterID=character_id, kills=filter_option)

    else:
        query = losses.query_total(alliance_ids, days_ago=days_ago, kills=filter_option)

    oldest_record = losses.oldest_record(alliance_ids, filter_option)

    if oldest_record:
        days_stored = current_time - oldest_record

    else:
        days_stored = None

    for ship in query:

        if ship[0] == 0:
            continue

        ship_name = utils.lookup_typename(ship[0])

        total_ships_lost += ship[1]

        if ship_name not in ships_lost:
            ships_lost[ship_name] = ship[1]



    return render_template('stats/ships.html', config_coalitions=config['coalitions'],
                                               coalition=coalition,
                                               ships_lost=ships_lost,
                                               days=days,
                                               oldest_record=oldest_record,
                                               days_stored=days_stored.days,
                                               character=character,
                                               total_ships_lost=total_ships_lost,
                                               filter_option=filter_option,
                                               name=config['project_name'])

if __name__ == '__main__':
    app.run()
