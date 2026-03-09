import logging
import ipaddress
from functools import lru_cache
from typing import Union, Optional, Dict, Any

import geoip2
import geoip2.database
import maxminddb

from mongoose.core.registry import JobRegistry
from mongoose.models import NetworkDPI, NetworkFlow, NetworkAlert
from mongoose.models.configuration import GeoIPConfiguration
from mongoose.utils.exceptions import IgnoreCacheException
from mongoose.utils.jobs import DailyFileDownloadJob

logger = logging.getLogger(__name__)


class IP66GeoIP:
    database_filename = "ip66.mmdb"
    database_url = "https://downloads.ip66.dev/db/ip66.mmdb"
    download_job = None

    def __init__(self, geoip_configuration: GeoIPConfiguration):
        self.geoip_configuration = geoip_configuration
        self.database_path = self.geoip_configuration.maxmind_db_path / self.database_filename
        if not self.download_job:
            self.download_job = DailyFileDownloadJob(url=self.database_url, local_path=self.database_path)
            JobRegistry().register(self.download_job)

    @lru_cache(maxsize=512)
    def request_geoip(self, ip_address: str) -> Optional[Dict[Any, Any]]:
        reader = maxminddb.open_database(str(self.database_path))
        geoip_data = {}
        record = reader.get(ip_address)

        if not record or not record.get("autonomous_system_number", None):
            raise IgnoreCacheException()  # prevents caching

        geoip_data["details"] = record.get("anonymous_ip", None)
        geoip_data["traits"] = record.get("traits", None)
        geoip_data["asn"] = record.get("autonomous_system_number")
        geoip_data["organization"] = record.get("autonomous_system_organization")
        geoip_data["country"] = record.get("country", {}).get("iso_code")
        geoip_data["country_name"] = record.get("country", {}).get("names", {}).get("en")
        geoip_data["continent"] = record.get("continent", {}).get("code")
        geoip_data["continent_name"] = record.get("continent", {}).get("names", {}).get("en")

        if geoip_data:
            return geoip_data
        raise IgnoreCacheException()  # prevents caching

    def enrich_network_event(self, event: Union[NetworkDPI, NetworkFlow, NetworkAlert]):
        if not hasattr(event, "src_ip") or not hasattr(event, "dst_ip"):
            return

        src_ip = ipaddress.ip_address(event.src_ip)
        dst_ip = ipaddress.ip_address(event.dst_ip)
        if src_ip.is_global:
            try:
                event.enrichment["geoip"] = self.request_geoip(event.src_ip)
                event.enrichment["geoip"]["ip"] = event.src_ip
            except (Exception,):
                pass
        elif dst_ip.is_global:
            try:
                event.enrichment["geoip"] = self.request_geoip(event.dst_ip)
                event.enrichment["geoip"]["ip"] = event.dst_ip
            except (Exception,):
                pass


class MaxMindGeoIP:
    def __init__(self, geoip_configuration: GeoIPConfiguration):
        self.geoip_configuration = geoip_configuration
        self.databases = []
        self.list_databases()

    def list_databases(self):
        if not self.geoip_configuration.maxmind_db_path.exists():
            return

        for db in self.geoip_configuration.maxmind_db:
            db_path = self.geoip_configuration.maxmind_db_path / db
            if not db_path.exists():
                continue
            self.databases.append(str(db_path))

    def _get_asn_info(self, geoip_reader: geoip2.database.Reader, ip_address: str):
        try:
            data = geoip_reader.asn(ip_address)
            return {
                "asn": data.autonomous_system_number,
                "organization": data.autonomous_system_organization,
            }
        except (Exception,) as e:
            return {}

    def _get_country_info(self, geoip_reader: geoip2.database.Reader, ip_address: str):
        try:
            data = geoip_reader.country(ip_address)
            return {
                "country": data.country.iso_code,
                "country_name": data.country.name,
                "continent": data.country.continent.code,
                "continent_name": data.country.continent.name,
            }
        except (Exception,) as e:
            return {}

    def _get_city_info(self, geoip_reader: geoip2.database.Reader, ip_address: str):
        try:
            data = geoip_reader.city(ip_address)
            return {
                "city": data.city.name,
                "country": data.country.iso_code,
                "country_name": data.country.name,
                "continent": data.continent.code,
                "continent_name": data.continent.name,
                "latitude": data.location.latitude,
                "longitude": data.location.longitude,
                "timezone": data.location.time_zone,
                "accuracy_radius": data.location.accuracy_radius,
            }
        except (Exception,) as e:
            return {}

    @lru_cache(maxsize=512)
    def request_geoip(self, ip_address: str) -> Optional[Dict[Any, Any]]:
        geoip_data = {}
        for db in self.databases:
            with geoip2.database.Reader(db) as geoip:
                if "ASN" in db:
                    _d = self._get_asn_info(geoip, ip_address)
                    logger.debug(f"GeoIP ASN {_d}")
                    geoip_data.update(_d)
                if "Country" in db:
                    _d = self._get_country_info(geoip, ip_address)
                    logger.debug(f"GeoIP Country {_d}")
                    geoip_data.update(_d)
                if "City" in db:
                    _d = self._get_city_info(geoip, ip_address)
                    logger.debug(f"GeoIP City {_d}")
                    geoip_data.update(_d)

        if geoip_data:
            return geoip_data
        raise IgnoreCacheException()  # prevents caching

    def enrich_network_event(self, event: Union[NetworkDPI, NetworkFlow, NetworkAlert]):
        if not hasattr(event, "src_ip") or not hasattr(event, "dst_ip"):
            return

        src_ip = ipaddress.ip_address(event.src_ip)
        dst_ip = ipaddress.ip_address(event.dst_ip)
        if src_ip.is_global:
            try:
                event.enrichment["geoip"] = self.request_geoip(event.src_ip)
                event.enrichment["geoip"]["ip"] = event.src_ip
            except (Exception,):
                pass
        elif dst_ip.is_global:
            try:
                event.enrichment["geoip"] = self.request_geoip(event.dst_ip)
                event.enrichment["geoip"]["ip"] = event.dst_ip
            except (Exception,):
                pass
