from flask import Flask, render_template, request, redirect, url_for, jsonify
#from flask_sqlalchemy import SQLAlchemy
import os
import gpxpy
import gpxpy.gpx
import math
from datetime import datetime, date
from models import db_connect, create_table, Track, Coordinate, Driver, Vehicle
from sqlalchemy.orm import sessionmaker

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/gpx_data.db'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

session = sessionmaker(bind=db_connect())()
create_table(db_connect())
# Ensure the upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

def parse_gpx(file_path):
    """Parses a GPX file and extracts coordinates."""
    with open(file_path, 'r') as gpx_file:
        gpx = gpxpy.parse(gpx_file)

        coordinates = []
        start_time = None
        end_time = None
        
        #print(gpx)
        tracks = []
        for waypoint in gpx.waypoints:
            coordinates.append((waypoint.latitude,waypoint.longitude,waypoint.elevation,0.0,waypoint.time))
            trackname = waypoint.name if not waypoint.name is None else 'Wegpunkte'
            if start_time is None or waypoint.time < start_time:
               start_time = waypoint.time
            if end_time is None or waypoint.time > end_time:
               end_time = waypoint.time
        if not coordinates == []:
          if trackname != 'Wegpunkte' and trackname[0].isdigit() and trackname[-1].isdigit():
            trackname = 'Wegpunkte'
          tracks.append((coordinates,start_time,end_time,trackname,'Wegpunkt')) 

        for track in gpx.tracks:
            coordinates = []
            start_time = None
            end_time = None
            trackname = track.name if not track.name is None else 'Strecke'
            for segment in track.segments:
                for point in segment.points:
                    coordinates.append((point.latitude, point.longitude,point.elevation, point.speed, point.time))
                    if start_time is None or point.time < start_time:
                        start_time = point.time
                    if end_time is None or point.time > end_time:
                        end_time = point.time
            if trackname != 'Strecke' and trackname[0].isdigit() and trackname[-1].isdigit():
              trackname = 'Strecke'
            tracks.append((coordinates,start_time,end_time,trackname,'Strecke'))

        return tracks#coordinates, start_time, end_time, trackname

def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance between two points on the Earth."""
    R = 6371  # Earth radius in kilometers
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
    
def calculate_total_distance(coordinates):
  total_distance = 0
  if len(coordinates) > 1:
    distances = []
    for i in range(1, len(coordinates)):
       lat1, lon1 = coordinates[i-1][0], coordinates[i-1][1]
       lat2, lon2 = coordinates[i][0], coordinates[i][1]
       distance = haversine(lat1, lon1, lat2, lon2)
       distances.append(distance)
    total_distance = round(sum(distances),2)
    
  return total_distance
  
def calculate_avg_speed(total_distance, start_time, end_time):
  avg_speed = 0
  if total_distance != 0 and start_time is not None and end_time is not None:
    track_time = (end_time - start_time).total_seconds()/3600 #Umwandlung von Sekunden in Stunden
    #print(track_time)
    avg_speed = round(total_distance/track_time,2)
  return avg_speed

@app.route('/')
def index():
    vehicles = session.query(Vehicle.name).distinct().all()
    drivers = session.query(Driver.name).distinct().all()
    return render_template('index.html', vehicles=vehicles, drivers=drivers)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return redirect(url_for('index'))

    file = request.files['file']
    if file.filename == '':
        return redirect(url_for('index'))

    if file:
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file_check = session.query(Track).filter(Track.file_path == file_path).first()
        if file_check:
          return redirect(url_for('index'))
        else:
          file.save(file_path)

          # Parse GPX and save data to database
          for coordinates,start_time,end_time,track_name,type in parse_gpx(file_path):
#          coordinates, start_time, end_time, track_name = parse_gpx(file_path)
            splitted_filename = file.filename.split('_')
            driver_name = splitted_filename[0]#request.form.get('vehicle')
            vehicle_name = splitted_filename[1]#request.form.get('driver')

            vehicle = session.query(Vehicle).filter(Vehicle.name == vehicle_name).first()
            driver = session.query(Driver).filter(Driver.name == driver_name).first()
            if not driver:
              driver = Driver(name=driver_name)
              session.add(driver)
              session.flush()
            if not vehicle:
              vehicle = Vehicle(name=vehicle_name)
              session.add(vehicle)
              session.flush()
            #date = request.form.get('date')
            track_date = date(start_time.year,start_time.month,start_time.day) if not start_time is None else None
            
            total_distance =0
            avg_speed=0
            if len(coordinates) > 1:
              total_distance = calculate_total_distance(coordinates)
              if type == 'Strecke':
                avg_speed = calculate_avg_speed(total_distance, start_time, end_time)

            track = Track(name=track_name, file_path=file_path, vehicle_id=vehicle.id, driver_id=driver.id, date=track_date,total_distance= total_distance,avg_speed=avg_speed, start_time=start_time, end_time=end_time)
            session.add(track)
            session.commit()

            for lat, lon,ele, speed, time in coordinates:
                coord = Coordinate(lat=lat, lon=lon, ele=ele,speed=speed, time=time, track_id=track.id)
                session.add(coord)
            session.commit()

          return redirect(url_for('index'))

@app.route('/filter', methods=['GET', 'POST'])
def filter_tracks():
    vehicle_name = request.form.get('vehicle')
    driver_name = request.form.get('driver')
    date_from = request.form.get('date_from')
    date_to = request.form.get('date_to')

    query = session.query(Driver.name,Track.id,Track.name,Track.date,Vehicle.name).join(Track, Driver.id == Track.driver_id).join(Vehicle, Track.vehicle_id == Vehicle.id)

    #query = session.query(Track).join(Vehicle).join(Driver)
    if vehicle_name:
        query = query.filter(Vehicle.name == vehicle_name)
    if driver_name:
        query = query.filter(Driver.name == driver_name)
    if date_from:
        query = query.filter(Track.date >= date_from)
    if date_to:
        query = query.filter(Track.date <= date_to)

    tracks = query.order_by(Track.date.asc()).all()
    driver_combinations = {}
    for track in tracks:
        driver = track[0]
        vehicle = track[-1]
        if driver not in driver_combinations:
            driver_combinations[driver] = {}
        if vehicle not in driver_combinations[driver]:
            driver_combinations[driver][vehicle] = []
        driver_combinations[driver][vehicle].append(track[1:-1])
    #print(driver_combinations)
    return render_template('filtered_tracks.html', tracks = driver_combinations)

@app.route('/track/<int:track_id>')
def view_track(track_id):
    track = session.query(Track).filter(Track.id == track_id).first()
    coordinates = [{'lat': coord.lat, 'lon': coord.lon, 'speed': coord.speed, 'time': coord.time} for coord in track.coordinates]
    total_distance = track.total_distance
    avg_speed = track.avg_speed

    if len(coordinates) > 1:
        distances = []
        for i in range(1, len(coordinates)):
            lat1, lon1 = coordinates[i-1]['lat'], coordinates[i-1]['lon']
            lat2, lon2 = coordinates[i]['lat'], coordinates[i]['lon']
            distance = haversine(lat1, lon1, lat2, lon2)
            distances.append(distance)
        total_distance = round(sum(distances),2)

        valid_speeds = [coord['speed'] for coord in coordinates if coord['speed']]
        if valid_speeds:
            avg_speed = sum(valid_speeds) / len(valid_speeds)
            avg_speed = round(avg_speed,2)

    return render_template('view_track.html', track=track, driver= track.driver, vehicle=track.vehicle,coordinates=coordinates, total_distance=total_distance, avg_speed=avg_speed)

if __name__ == '__main__':
    #with app.app_context():
        #db.drop_all()
        #db.create_all()
    #app.run(host='0.0.0.0',debug=True,port=5000)
    app.run(debug=True)
