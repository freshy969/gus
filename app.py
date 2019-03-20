from flask import Flask, request, redirect, url_for, render_template, Response, jsonify, abort, session
from flask_restful import Api, Resource
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS, cross_origin
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from time import sleep
from googleapiclient.discovery import build
import os, secrets, spotipy, pylast, pprint, deezer, tidalapi
import spotipy.oauth2 as oauth2

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL')
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

from models import User, Song

spotify_secret = os.environ.get('SPOTIFY_SECRET')
spotify_id = os.environ.get('SPOTIFY_ID')
lastfm_secret = os.environ.get('LASTFM_SECRET')
lastfm_id = os.environ.get('LASTFM_KEY')
deezer_secret = os.environ.get('DEEZER_SECRET')
deezer_id = os.environ.get('DEEZER_ID')
tidal_secret = os.environ.get('TIDAL_PASSWORD')
tidal_id = os.environ.get('TIDAL_LOGIN')
google_id = os.environ.get('GOOGLE_KEY')
soundcloud_id = os.environ.get('CX_SOUNDCLOUD')
pandora_id = os.environ.get('CX_PANDORA')


credentials = oauth2.SpotifyClientCredentials(
        client_id=spotify_id,
        client_secret=spotify_secret)

token = credentials.get_access_token()
spotify = spotipy.Spotify(auth=token)

lastfm = pylast.LastFMNetwork(api_key=lastfm_id, api_secret=lastfm_secret)

deezerClient = deezer.Client()

tidal = tidalapi.Session()
tidal.login(tidal_id, tidal_secret)


pp = pprint.PrettyPrinter(indent=4)

def google_search(search_term, api_key, cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key)
    res = service.cse().list(q=search_term, cx=cse_id, **kwargs).execute()
    return res

@app.route('/', methods=['GET', 'POST'])
def homepage():
    error = None
    if request.method == 'POST':
        name = request.form['name']
        toggle = request.form['toggle']
        results = spotify.search(q=toggle + ':' + name, type=toggle, limit=10)
        count = 0
        data = []
        #print(results)

        if toggle == 'track':
            for i in results['tracks']['items']:
                if len(results['tracks']['items'][count]['album']['images']) == 0:
                    data.append({"img": "static/img/note.png",
                                 "name": results['tracks']['items'][count]['name'],
                                 "artist": results['tracks']['items'][count]['album']['artists'][0]['name'],
                                 "spotifyid": results['tracks']['items'][count]['id']})
                else:
                    data.append({"img": results['tracks']['items'][count]['album']['images'][0]['url'],
                                "name": results['tracks']['items'][count]['name'],
                                "artist": results['tracks']['items'][count]['album']['artists'][0]['name'],
                                "spotifyid": results['tracks']['items'][count]['id']})
                count += 1

        elif toggle == 'artist':
            for i in results['artists']['items']:
                if len(results['artists']['items'][count]['images']) == 0:
                    data.append({"img": "static/img/note.png",
                                 "name": results['artists']['items'][count]['name'],
                                 "artist": results['artists']['items'][count]['name'],
                                 "spotifyid": results['artists']['items'][count]['id']})
                else:
                    data.append({"img": results['artists']['items'][count]['images'][0]['url'],
                                "name": results['artists']['items'][count]['name'],
                                "artist": results['artists']['items'][count]['name'],
                                "spotifyid": results['artists']['items'][count]['id']})
                count += 1
        else:
            for i in results['albums']['items']:
                if len(results['albums']['items'][count]['images']) == 0:
                    data.append({"img": "static/img/note.png",
                                 "name": results['albums']['items'][count]['name'],
                                 "artist": results['albums']['items'][count]['artists'][0]['name'],
                                 "spotifyid": results['albums']['items'][count]['id']})
                else:
                    data.append({"img": results['albums']['items'][count]['images'][0]['url'],
                                "name": results['albums']['items'][count]['name'],
                                "artist": results['albums']['items'][count]['artists'][0]['name'],
                                "spotifyid": results['albums']['items'][count]['id']})
                count += 1
        #print(data)
        # make dict with limit of ten: img, name, artist
        # [ {img, name, artist}, {img, name, artist} ]
        return render_template('home.html', data=data, type=toggle)
    return render_template('home.html', error=error)

def generateKey():
    key = secrets.token_urlsafe(6)
    while(db.session.query(Song).filter(Song.url == key).count() != 0):
       key = secrets.token_urlsafe(6)
    return key

@app.route('/create/<type>/<spotifyid>')
def create(type, spotifyid):
    key = generateKey()
    soundcloud = "#"
    pandora = "#"
    if type == "album":
        result = spotify.album(spotifyid)
        album = result['name']
        artist = result['artists'][0]['name']
        lstfm = lastfm.get_album(artist, album).get_url()[26:]
        deez = deezerClient.advanced_search({"artist": artist, "album": album}, relation="album")
        deez = "album/" + str(deez[0].asdict()['id'])
        tid = tidal.search('album', album)
        for i in tid.albums:
            if i.name.lower().strip() == album.lower().strip() and i.artist.name.lower().strip() == artist.lower().strip():
                tide = "album/" + str(i.id)
                break
        result = google_search(album + " by " + artist, google_id, soundcloud_id)
        for i in result['items']:
            if '/sets/' in i['link']:
                soundcloud = i['link'][23:]
                break
        result = google_search(album + " by " + artist, google_id, pandora_id)
        for i in result['items']:
            pandora = i['link'][31:]
            break
    elif type == "track":
        result = spotify.track(spotifyid)
        album = result['album']['name']
        track = result['name']
        artist = result['artists'][0]['name']
        lstfm = lastfm.get_track(artist, track).get_url()[26:]
        deez = deezerClient.advanced_search({"artist": artist, "album": album, "track": track}, relation="track")
        deez = "track/" + str(deez[0].asdict()['id'])
        tid = tidal.search('track', track)
        for i in tid.tracks:
            if i.name.lower().strip() == track.lower().strip() and i.artist.name.lower().strip() == artist.lower().strip():
                tide = "track/" + str(i.id)
                break
        result = google_search(track + " by " + artist, google_id, soundcloud_id)
        for i in result['items']:
            soundcloud = i['link'][23:]
            break
        result = google_search(track + " by " + artist, google_id, pandora_id)
        for i in result['items']:
            pandora = i['link'][31:]
            break
    elif type == "artist":
        result = spotify.artist(spotifyid)
        artist = result['name']
        lstfm = lastfm.get_artist(artist).get_url()[26:]
        deez = deezerClient.advanced_search({"artist": artist}, relation="artist")
        deez = "artist/" + str(deez[0].asdict()['id'])
        tid = tidal.search('artist', artist)
        for i in tid.artists:
            if i.name.lower().strip() == artist.lower().strip():
                tide = "artist/" + str(i.id)
                break
        # Unable to do SoundCloud for artist
        result = google_search(artist, google_id, pandora_id)
        for i in result['items']:
            pandora = i['link'][31:]
            break
    song = Song(url=key, type=type, spotifyid=spotifyid, lastfm=lstfm, deezer=deez, tidal=tide, soundcloud=soundcloud, pandora=pandora)
    db.session.add(song)
    db.session.commit()
    return redirect(url_for('load', url=key))

@app.route('/s/<url>')
def load(url):
    song = db.session.query(Song).filter(Song.url == url)
    if(song.count() == 0):
        return "404 url not in database"
    else:
        if song[0].soundcloud == "#":
            return '<a href="https://open.spotify.com/' + song[0].type + '/'+ song[0].spotifyid+'">https://open.spotify.com/' + song[0].type + '/'+ song[0].spotifyid + '</a><br><a href="https://www.last.fm/music/' + song[0].lastfm + '">https://www.last.fm/music/' + song[0].lastfm + '</a>' + '<br><a href="https://www.deezer.com/' + song[0].deezer + '">https://www.deezer.com/' + song[0].deezer + '</a>' + '<br><a href="https://tidal.com/browse/' + song[0].tidal + '">https://tidal.com/browse/' + song[0].tidal + '</a>' + '<br><a href="https://pandora.com/artist/' + song[0].pandora + '">https://pandora.com/artist/' + song[0].pandora + '</a>'
        else:
            return '<a href="https://open.spotify.com/' + song[0].type + '/'+ song[0].spotifyid+'">https://open.spotify.com/' + song[0].type + '/'+ song[0].spotifyid + '</a><br><a href="https://www.last.fm/music/' + song[0].lastfm + '">https://www.last.fm/music/' + song[0].lastfm + '</a>' + '<br><a href="https://www.deezer.com/' + song[0].deezer + '">https://www.deezer.com/' + song[0].deezer + '</a>' + '<br><a href="https://tidal.com/browse/' + song[0].tidal + '">https://tidal.com/browse/' + song[0].tidal + '</a>' + '<br><a href="https://soundcloud.com/' + song[0].soundcloud + '">https://soundcloud.com/' + song[0].soundcloud + '</a>' + '<br><a href="https://pandora.com/artist/' + song[0].pandora + '">https://pandora.com/artist/' + song[0].pandora + '</a>'

if __name__ == '__main__':
    app.run()