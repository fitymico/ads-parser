#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Генерация SQL из спасённого ads_list.json"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Ad
from export.sql_export import (
    ad_to_sql_insert, get_city_id, get_region_id,
)
from datetime import datetime


def restore_sql(ads_json_path: str, output_path: str, user_id: int = 4173):
    with open(ads_json_path, 'r') as f:
        ads_list = json.load(f)

    print(f"Загружено {len(ads_list)} объявлений из {ads_json_path}")

    with open(output_path, 'w', encoding='utf-8') as out:
        out.write("-- SQL Export restored from ads_list.json\n")
        out.write(f"-- Generated: {datetime.now().isoformat()}\n")
        out.write(f"-- Total ads: {len(ads_list)}\n\n")
        out.write("SET NAMES utf8mb4;\n\n")

        count = 0
        for item in ads_list:
            ad_dict = item['ad']
            category_id = item['category_id']

            ad = Ad(**{k: v for k, v in ad_dict.items() if k in Ad.__dataclass_fields__})

            city_id = get_city_id(ad.city) if ad.city else 0
            region_id = get_region_id(ad.region) if ad.region else 0

            sql = ad_to_sql_insert(
                ad,
                category_id=category_id,
                city_id=city_id,
                region_id=region_id,
                user_id=user_id,
            )

            out.write(f"-- Ad: {ad.id}\n")
            out.write(sql)
            out.write("\n\n")
            count += 1

            if count % 10000 == 0:
                print(f"  {count}/{len(ads_list)}...")

        out.write(f"\n-- Export complete: {count} ads\n")

    print(f"SQL сохранён: {output_path} ({count} объявлений)")


if __name__ == "__main__":
    ads_path = sys.argv[1] if len(sys.argv) > 1 else "/data/ads_list.json"
    sql_path = sys.argv[2] if len(sys.argv) > 2 else "/data/export.sql"
    restore_sql(ads_path, sql_path)
