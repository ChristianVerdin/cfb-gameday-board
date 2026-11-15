"""NFL 2026 venue table keyed by ESPN venue.id (string).

Retrieved 2026-11-15. Coordinates: Wikidata P625 (CC0) via the public Wikidata API, cross-checked
against Wikipedia coordinates and a one-off geocoder spot check (values compared, no geocoder data
stored). Elevations: Wikipedia infobox values only; None where no source verifies one.
ESPN ids and indoor flags: 2026 regular-season scoreboards (weeks 1-12, 16, 18).
verified: '2src' = Wikidata agrees with an independent check within 0.5 km; '1src' = one usable
source only. SoFi keeps the Wikipedia/spot-check point (Wikidata sits about 0.3 km off).
roof: open | canopy (roof over seats, field open) | retractable | dome (fixed).
espn_indoor is ESPN's static flag; it is true for all retractables and does not mean the roof is closed.
"""
from __future__ import annotations

VENUES: dict[str, dict] = {
    "3673": dict(id="3673", name='Lumen Field', espn_name='Lumen Field', city='Seattle', region='WA', country='US',
        lat=47.5953, lon=-122.3317, tz='America/Los_Angeles', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q612736', 'wikipedia', 'osm-check']),
    "9119": dict(id="9119", name='Melbourne Cricket Ground', espn_name='Melbourne Cricket Ground', city='Melbourne', region='VIC', country='AU',
        lat=-37.8199, lon=144.9834, tz='Australia/Melbourne', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q330136', 'wikipedia', 'osm-check']),
    "3874": dict(id="3874", name='Paycor Stadium', espn_name='Paycor Stadium', city='Cincinnati', region='OH', country='US',
        lat=39.0954, lon=-84.516, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q1632294', 'wikipedia', 'osm-check']),
    "3727": dict(id="3727", name='Ford Field', espn_name='Ford Field', city='Detroit', region='MI', country='US',
        lat=42.34, lon=-83.0456, tz='America/New_York', roof='dome', espn_indoor=True, elev_ft=None,
        verified='2src', sources=['wikidata:Q1142586', 'wikipedia', 'osm-check']),
    "3810": dict(id="3810", name='Nissan Stadium', espn_name='Nissan Stadium', city='Nashville', region='TN', country='US',
        lat=36.1664, lon=-86.7714, tz='America/Chicago', roof='open', espn_indoor=False, elev_ft=450,
        verified='2src', sources=['wikidata:Q1142992', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "3812": dict(id="3812", name='Lucas Oil Stadium', espn_name='Lucas Oil Stadium', city='Indianapolis', region='IN', country='US',
        lat=39.7601, lon=-86.1638, tz='America/Indiana/Indianapolis', roof='retractable', espn_indoor=True, elev_ft=None,
        verified='2src', sources=['wikidata:Q867160', 'wikipedia', 'osm-check']),
    "3752": dict(id="3752", name='Acrisure Stadium', espn_name='Acrisure Stadium', city='Pittsburgh', region='PA', country='US',
        lat=40.4467, lon=-80.0158, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q1067148', 'wikipedia', 'osm-check']),
    "3628": dict(id="3628", name='Bank of America Stadium', espn_name='Bank of America Stadium', city='Charlotte', region='NC', country='US',
        lat=35.2258, lon=-80.8528, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q806673', 'wikipedia', 'osm-check']),
    "3712": dict(id="3712", name='EverBank Stadium', espn_name='EverBank Stadium', city='Jacksonville', region='FL', country='US',
        lat=30.3239, lon=-81.6375, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q635117', 'wikipedia', 'osm-check']),
    "3891": dict(id="3891", name='NRG Stadium', espn_name='Reliant Stadium', city='Houston', region='TX', country='US',
        lat=29.6847, lon=-95.4108, tz='America/Chicago', roof='retractable', espn_indoor=True, elev_ft=None,
        verified='2src', sources=['wikidata:Q1058864', 'wikipedia', 'osm-check']),
    "6501": dict(id="6501", name='Allegiant Stadium', espn_name='Allegiant Stadium', city='Las Vegas', region='NV', country='US',
        lat=36.0908, lon=-115.183, tz='America/Los_Angeles', roof='dome', espn_indoor=True, elev_ft=2190,
        verified='2src', sources=['wikidata:Q27768421', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "5239": dict(id="5239", name='U.S. Bank Stadium', espn_name='U.S. Bank Stadium', city='Minneapolis', region='MN', country='US',
        lat=44.9739, lon=-93.2581, tz='America/Chicago', roof='dome', espn_indoor=True, elev_ft=None,
        verified='2src', sources=['wikidata:Q7929512', 'wikipedia', 'osm-check']),
    "3806": dict(id="3806", name='Lincoln Financial Field', espn_name='Lincoln Financial Field', city='Philadelphia', region='PA', country='US',
        lat=39.9009, lon=-75.1678, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q1052370', 'wikipedia', 'osm-check']),
    "7065": dict(id="7065", name='SoFi Stadium', espn_name='SoFi Stadium', city='Inglewood', region='CA', country='US',
        lat=33.953, lon=-118.339, tz='America/Los_Angeles', roof='canopy', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q19520501', 'wikipedia', 'osm-check']),
    "3839": dict(id="3839", name='MetLife Stadium', espn_name='MetLife Stadium', city='East Rutherford', region='NJ', country='US',
        lat=40.8136, lon=-74.0744, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=7,
        verified='2src', sources=['wikidata:Q10862290', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "3622": dict(id="3622", name='Arrowhead Stadium', espn_name='Arrowhead Stadium', city='Kansas City', region='MO', country='US',
        lat=39.0489, lon=-94.4839, tz='America/Chicago', roof='open', espn_indoor=False, elev_ft=840,
        verified='2src', sources=['wikidata:Q544553', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "11938": dict(id="11938", name='Highmark Stadium', espn_name='Highmark Stadium', city='Orchard Park', region='NY', country='US',
        lat=42.773, lon=-78.7922, tz='America/New_York', roof='canopy', espn_indoor=False, elev_ft=770,
        verified='2src', sources=['wikidata:Q16251517', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "5348": dict(id="5348", name='Mercedes-Benz Stadium', espn_name='Mercedes-Benz Stadium', city='Atlanta', region='GA', country='US',
        lat=33.7553, lon=-84.4008, tz='America/New_York', roof='retractable', espn_indoor=True, elev_ft=None,
        verified='2src', sources=['wikidata:Q7007552', 'wikipedia', 'osm-check']),
    "3933": dict(id="3933", name='Soldier Field', espn_name='Soldier Field', city='Chicago', region='IL', country='US',
        lat=41.8625, lon=-87.6167, tz='America/Chicago', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q1132413', 'wikipedia', 'osm-check']),
    "3738": dict(id="3738", name='Gillette Stadium', espn_name='Gillette Stadium', city='Foxborough', region='MA', country='US',
        lat=42.0909, lon=-71.2643, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q373355', 'wikipedia', 'osm-check']),
    "3886": dict(id="3886", name='Raymond James Stadium', espn_name='Raymond James Stadium', city='Tampa', region='FL', country='US',
        lat=27.9758, lon=-82.5033, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q1141343', 'wikipedia', 'osm-check']),
    "3814": dict(id="3814", name='M&T Bank Stadium', espn_name='M&T Bank Stadium', city='Baltimore', region='MD', country='US',
        lat=39.2781, lon=-76.6228, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q1141336', 'wikipedia', 'osm-check']),
    "3937": dict(id="3937", name='Empower Field at Mile High', espn_name='Empower Field at Mile High', city='Denver', region='CO', country='US',
        lat=39.7439, lon=-105.02, tz='America/Denver', roof='open', espn_indoor=False, elev_ft=5280,
        verified='2src', sources=['wikidata:Q1046135', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "3687": dict(id="3687", name='AT&T Stadium', espn_name='AT&T Stadium', city='Arlington', region='TX', country='US',
        lat=32.7477, lon=-97.0929, tz='America/Chicago', roof='retractable', espn_indoor=True, elev_ft=None,
        verified='2src', sources=['wikidata:Q838284', 'wikipedia', 'osm-check']),
    "3970": dict(id="3970", name='State Farm Stadium', espn_name='State Farm Stadium', city='Glendale', region='AZ', country='US',
        lat=33.5275, lon=-112.2625, tz='America/Phoenix', roof='retractable', espn_indoor=True, elev_ft=1060,
        verified='2src', sources=['wikidata:Q756433', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "4738": dict(id="4738", name="Levi's Stadium", espn_name="Levi's Stadium", city='Santa Clara', region='CA', country='US',
        lat=37.4034, lon=-121.97, tz='America/Los_Angeles', roof='open', espn_indoor=False, elev_ft=16,
        verified='2src', sources=['wikidata:Q7419343', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "3798": dict(id="3798", name='Lambeau Field', espn_name='Lambeau Field', city='Green Bay', region='WI', country='US',
        lat=44.5014, lon=-88.0622, tz='America/Chicago', roof='open', espn_indoor=False, elev_ft=640,
        verified='2src', sources=['wikidata:Q860790', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    "3679": dict(id="3679", name='Huntington Bank Field', espn_name='Huntington Bank Field', city='Cleveland', region='OH', country='US',
        lat=41.5061, lon=-81.6994, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q1100756', 'wikipedia', 'osm-check']),
    "3948": dict(id="3948", name='Hard Rock Stadium', espn_name='Hard Rock Stadium', city='Miami Gardens', region='FL', country='US',
        lat=25.9581, lon=-80.2389, tz='America/New_York', roof='canopy', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q864339', 'wikipedia', 'osm-check']),
    "3719": dict(id="3719", name='Northwest Stadium', espn_name='Northwest Stadium', city='Landover', region='MD', country='US',
        lat=38.9078, lon=-76.8644, tz='America/New_York', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q583085', 'wikipedia', 'osm-check']),
    "3493": dict(id="3493", name='Caesars Superdome', espn_name='Caesars Superdome', city='New Orleans', region='LA', country='US',
        lat=29.9508, lon=-90.0811, tz='America/Chicago', roof='dome', espn_indoor=True, elev_ft=None,
        verified='2src', sources=['wikidata:Q756452', 'wikipedia', 'osm-check']),
    "11931": dict(id="11931", name='Maracana Stadium', espn_name='Maracanã Stadium', city='Rio de Janeiro', region='', country='BR',
        lat=-22.9122, lon=-43.2303, tz='America/Sao_Paulo', roof='canopy', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q155174', 'wikipedia', 'osm-check']),
    "5534": dict(id="5534", name='Tottenham Hotspur Stadium', espn_name='Tottenham Hotspur Stadium', city='London', region='', country='GB',
        lat=51.6044, lon=-0.0664, tz='Europe/London', roof='open', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q55074091', 'wikipedia', 'osm-check']),
    "2455": dict(id="2455", name='Wembley Stadium', espn_name='Wembley Stadium', city='London', region='', country='GB',
        lat=51.5556, lon=-0.2794, tz='Europe/London', roof='canopy', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q128468', 'wikipedia', 'osm-check']),
    "1781": dict(id="1781", name='Stade de France', espn_name='Stade de France', city='Saint-Denis', region='', country='FR',
        lat=48.9244, lon=2.36, tz='Europe/Paris', roof='canopy', espn_indoor=False, elev_ft=None,
        verified='1src', sources=['wikidata:Q13205', 'wikipedia']),
    "1353": dict(id="1353", name='Santiago Bernabeu', espn_name='Santiago Bernabéu', city='Madrid', region='', country='ES',
        lat=40.4531, lon=-3.6883, tz='Europe/Madrid', roof='retractable', espn_indoor=True, elev_ft=None,
        verified='2src', sources=['wikidata:Q164027', 'wikipedia', 'osm-check']),
    "11930": dict(id="11930", name='Allianz Arena', espn_name='FC Bayern Munich Stadium', city='Munich', region='', country='DE',
        lat=48.2188, lon=11.6248, tz='Europe/Berlin', roof='canopy', espn_indoor=False, elev_ft=None,
        verified='2src', sources=['wikidata:Q127429', 'wikipedia', 'osm-check']),
    "8219": dict(id="8219", name='Estadio Banorte', espn_name='Estadio Banorte', city='Mexico City', region='', country='MX',
        lat=19.3031, lon=-99.1506, tz='America/Mexico_City', roof='open', espn_indoor=False, elev_ft=7352,
        verified='2src', sources=['wikidata:Q320454', 'wikipedia', 'osm-check', 'wikipedia:elevation']),
    # Buffalo's old stadium; ESPN's team record still points here, 2026 games use 11938.
    "3883": dict(id="3883", name="Highmark Stadium (Old)", espn_name="Highmark Stadium (Old)", city="Orchard Park", region="NY", country="US",
        lat=None, lon=None, tz="America/New_York", roof="open", espn_indoor=False, elev_ft=None,
        verified="unverified", sources=[], retired=True),
}

for _v in VENUES.values():
    _v.setdefault("retired", False)

ACTIVE_IDS = tuple(k for k, v in VENUES.items() if not v["retired"])


def venue(venue_id) -> dict | None:
    """Venue row for an ESPN venue id (str or int), or None if unknown."""
    return VENUES.get(str(venue_id)) if venue_id is not None else None


def display_name(venue_id, espn_name: str = "") -> str:
    v = venue(venue_id)
    return v["name"] if v else (espn_name or "")


def roof(venue_id) -> str | None:
    v = venue(venue_id)
    return v["roof"] if v else None
