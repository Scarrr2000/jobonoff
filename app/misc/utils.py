from geopy.geocoders import Nominatim

# Получаем русское название адреса по широте и долготе
def get_address(latitude: float, longitude: float):
    geolocator = Nominatim(user_agent="geoapi")
    location = geolocator.reverse((latitude, longitude), exactly_one=True, language='ru')
    if location:
        return location.address
    else:
        return "Адрес не найден"