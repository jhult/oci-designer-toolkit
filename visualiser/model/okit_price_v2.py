
# Copyright (c) 2020, Oracle and/or its affiliates.
# Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl.

"""Provide Module Description
"""

import json
import requests
from model import shapes
from model import calculator
from model import streaming
import sys
import datetime
import os
from model import bom


import numpy as np
import pandas as pd
from io import BytesIO
from flask import Flask, send_file

oci_url = "https://itra.oraclecloud.com/itas/.anon/myservices/api/v1/products"
# aws_url = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/"


# all resources form OKIT
all_resources = []

# get all OCI prices


def get_oci_price_list(cloud, url):
    # headers = {'Content-type': 'application/json'}
    if cloud == 'oci':
        PARAMS = {'offset': "0", 'limit': "500"}
        res = requests.get(url, PARAMS)
        # print("status code: {}".format(res.status_code))
    elif cloud == 'aws':
        res = requests.get(url)
        # print("status code: {}".format(res.status_code))
    return res.json()

# read json generated by user
def load_json(filename):
    # print(filename)
    # print(type(filename))
    # OCI_resources
    resources = []
    # data = filename
    # for item in data:

    # Get all resource names
    for item in filename:
        resources.append(item)
    # remove non-OCI resources
    del resources[0:3]
    all_resources = resources[:-1]

    # Call pricing calculator
    OKIT_RESULTS = price_calculator(filename, all_resources)

    return OKIT_RESULTS[0]

# price calculation in saved json
# read json generated by user
def export_bom(filename):
    # print(filename)
    # print(type(filename))
    # OCI_resources
    resources = []
    # data = filename
    # for item in data:

    # Get all resource names
    filename = json.loads(filename)
    for item in filename:
        resources.append(item)
    # remove non-OCI resources
    del resources[0:3]
    all_resources = resources[:-1]

    print("\nStart the Process\n")
    # Call pricing calculator
    OKIT_RESULTS = price_calculator(filename, all_resources)
    print("\nEnd the Process\n")

    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    OKIT_RESULTS[1].to_excel(writer, startrow=0,index=False,
                          merge_cells=False, sheet_name="Sheet_1")
    workbook = writer.book
    worksheet = writer.sheets["Sheet_1"]
    format = workbook.add_format()
    format.set_bg_color('#eeeeee')
    worksheet.set_column(0, 9, 28)
    writer.close()
    output.seek(0)
    print(OKIT_RESULTS[1])
    return send_file(output, attachment_filename="BoM.xlsx", as_attachment=True, cache_timeout=0)

    # return OKIT_RESULTS

# price calculation in saved json


def price_calculator(okitjson, all_resources):
    # create/reset bom format whenever pricing list is called
    df = bom.create_bom()
    storage_per_month = 1
    ocpu_per_month = 24 * 31

    results = {}
    for oci_resource in all_resources:
        results.update({oci_resource: (0, 0)})

    print("==============================")
    print(" PAYG   Monthly_Flex ")

    #############################################
    # ADB price calculator
    #############################################
    if okitjson['autonomous_databases']:
        adb_storage = 0
        adb_ocpu = 0
        oltp_ocp = 0
        oltp_byol_ocp = 0
        oltp_storage = 0
        dw_byol_ocpu = 0
        dw_ocpu = 0
        dw_storage = 0
        for adb in okitjson['autonomous_databases']:
            adb_storage += float(adb['data_storage_size_in_tbs'])
            #adb_ocpu += float(adb['cpu_core_count'])
            license = str(adb['license_model']).upper()
            db_workload = str(adb['db_workload']).upper()

            if license == 'BRING_YOUR_OWN_LICENSE':
                if db_workload == 'DW':
                    dw_byol_ocpu += float(adb['cpu_core_count'])
                    dw_storage += float(adb['data_storage_size_in_tbs'])
                    #bom.update_bom(df, "B89039", dw_byol_ocpu, ocpu_per_month)
                elif db_workload == 'OLTP':
                    oltp_byol_ocp += float(adb['cpu_core_count'])
                    oltp_storage += float(adb['data_storage_size_in_tbs'])
                    #bom.update_bom(df, "B90454", oltp_byol_ocp, ocpu_per_month)
            elif license == 'LICENSE_INCLUDED':
                if db_workload == 'DW':
                    dw_ocpu += float(adb['cpu_core_count'])
                    dw_storage += float(adb['data_storage_size_in_tbs'])
                    #bom.update_bom(df, "B89040", dw_ocpu, ocpu_per_month)
                elif db_workload == 'OLTP':
                    oltp_ocp += float(adb['cpu_core_count'])
                    oltp_storage += float(adb['data_storage_size_in_tbs'])
                    # bom.update_bom(df, "B90453", oltp_ocp, ocpu_per_month)
            else:
                print("license_model is not defined")

        # get ADB storage per month
        adb_storage_price = calculator.get_oci_price_ords('B89041')
        PAYG_ADB_Storage, Monthly_Flex_ADB_Storage = calculator.TB_per_month(adb_storage_price, adb_storage)

        # get ocpu per hour
        adb_ocpu = dw_ocpu + oltp_ocp
        adb_byol_ocpu = dw_byol_ocpu + oltp_byol_ocp
        adb_ocpu_price = calculator.get_oci_price_ords('B89040')
        adb_byol_ocpu_price = calculator.get_oci_price_ords('B89039')

        PAYG_ADB_OCPU, Monthly_Flex_ADB_OCPU = calculator.OCPU_per_hr(adb_ocpu_price, adb_ocpu)
        PAYG_ADB_BYOL_OCPU, Monthly_Flex_ADB_BYOL_OCPU = calculator.OCPU_per_hr(adb_byol_ocpu_price, adb_byol_ocpu)


        PAYG_ADB_price = round(PAYG_ADB_Storage + PAYG_ADB_OCPU + PAYG_ADB_BYOL_OCPU, 2)
        Monthly_Flex_ADB_price = round(Monthly_Flex_ADB_Storage + Monthly_Flex_ADB_OCPU + Monthly_Flex_ADB_BYOL_OCPU, 2)
        print(PAYG_ADB_price, Monthly_Flex_ADB_price)

        # results.update({'autonomous_databases': (PAYG_ADB_price, Monthly_Flex_ADB_price)})
        # no more monthly and annual flex is same price as PAYG
        results.update({'autonomous_databases': (PAYG_ADB_price, PAYG_ADB_price)})

        print(dw_storage,oltp_storage,dw_ocpu,dw_ocpu,dw_byol_ocpu,oltp_ocp,oltp_byol_ocp)
        # parsing to bom format
        bom.update_bom(df, "B89041", dw_storage, storage_per_month)
        bom.update_bom(df, "B90455", oltp_storage, storage_per_month)
        bom.update_bom(df, "B89040", dw_ocpu, ocpu_per_month)
        bom.update_bom(df, "B90453", oltp_ocp, ocpu_per_month)
        bom.update_bom(df, "B89039", dw_byol_ocpu, ocpu_per_month)
        bom.update_bom(df, "B90454", oltp_byol_ocp, ocpu_per_month)

    else:
        results.update({'autonomous_databases': (0, 0)})

    #############################################
    # DBaaS price calculator
    #############################################
    if okitjson['database_systems']:
        dbaas_storage = 0
        dbaas_ocpu = 0
        PAYG_DBaaS_OCPU = 0
        Monthly_Flex_DBaaS_OCPU = 0
        base_dbaas_sku = ''
        additional_dbaas_sku = ''

        for dbaas in okitjson['database_systems']:
            node_count = dbaas['node_count']
            # print(node_count)
            shape = dbaas['shape']
            license_model = dbaas['license_model']
            OCPU, MEM, SSD, DBaaS_SKU = shapes.ComputeShape(shape)
            database_edition = dbaas['database_edition']
            dbaas_shape = str(shape[0:2]).lower()
            if dbaas_shape == "ex":
                dbaas_license_price = calculator.get_oci_price_ords(DBaaS_SKU)
                base_dbaas_sku = dbaas_license_price[2]
                # print(dbaas_license_price)
            else:
                dbaas_license_price = calculator.get_dbaas_license_price(
                    license_model, database_edition, dbaas_shape)
                base_dbaas_sku = dbaas_license_price[2]
                # print(dbaas_license_price)

            if node_count == 1:
                if dbaas_shape == "vm":
                    # Add up DB license per ocpu
                    PAYG, Monthly_Flex = calculator.OCPU_per_hr(
                        dbaas_license_price, OCPU)
                    # Non-RAC VM - 456GB storage will be added
                    dbaas_storage = int(dbaas['data_storage_size_in_gb']) + 456

                    # parsing to bom format
                    bom.update_bom(df, base_dbaas_sku, OCPU, ocpu_per_month)

                elif (dbaas_shape == "bm" or dbaas_shape == "ex"):
                    PAYG, Monthly_Flex, additional_dbaas_sku, additional_ocpu = calculator.BM_Exa_OCPU_per_hr(license_model, database_edition,
                                                                                                              dbaas_license_price, dbaas_shape,
                                                                                                              int(dbaas['cpu_core_count']))
                    # parsing to bom format
                    bom.update_bom(df, base_dbaas_sku, 1, ocpu_per_month)
                    bom.update_bom(df, additional_dbaas_sku,
                                   additional_ocpu, ocpu_per_month)

                # Add up DB license per ocpu
                PAYG_DBaaS_OCPU += PAYG
                Monthly_Flex_DBaaS_OCPU += Monthly_Flex

            else:
                # node count = 2
                # Add up DB license per ocpu
                PAYG, Monthly_Flex = calculator.OCPU_per_hr(
                    dbaas_license_price, OCPU)
                PAYG_DBaaS_OCPU += PAYG * 2
                Monthly_Flex_DBaaS_OCPU += Monthly_Flex * 2
                # parsing to bom format
                bom.update_bom(df, base_dbaas_sku, OCPU*2, ocpu_per_month)

                if dbaas_shape == "vm":
                    # RAC VM - DB license cose will be double/ 656GB storage will be added
                    dbaas_storage = int(dbaas['data_storage_size_in_gb']) + 656

        # DBaaS block storage price
        block_storage_price = calculator.get_oci_price_ords('B91961')
        # DBaaS vpus price
        vpus_ocpu_price = calculator.get_oci_price_ords('B91962')
        PAYG_DBaaS_volume_price, Monthly_Flex_DBaaS_volume_price = calculator.Block_volume_GB_per_month(
            block_storage_price, dbaas_storage, vpus_ocpu_price, 20)

        PAYG_DBaaS_price = round(PAYG_DBaaS_OCPU + PAYG_DBaaS_volume_price, 2)
        Monthly_Flex_DBaaS_price = round(
            Monthly_Flex_DBaaS_OCPU + Monthly_Flex_DBaaS_volume_price, 2)

        print(PAYG_DBaaS_price, Monthly_Flex_DBaaS_price)
        # results.update({'database_systems': (PAYG_DBaaS_price, Monthly_Flex_DBaaS_price)})
        # no more monthly and annual flex is same price as PAYG
        results.update({'database_systems': (PAYG_DBaaS_price, PAYG_DBaaS_price)})

        # parsing DBaaS storage to bom format
        bom.update_bom(df, 'B91961', dbaas_storage, storage_per_month)
        bom.update_bom(df, 'B91962', dbaas_storage * 20, storage_per_month)

    #############################################
    # Block Volume price calculator
    #############################################
    if okitjson['block_storage_volumes']:
        block_gb = 0
        vpus_per_gb = 0
        PAYG_Block_Volume_price = 0
        Monthly_Flex_Block_Volume_price = 0
        # get block volume price
        block_storage_price = calculator.get_oci_price_ords('B91961')
        # get vpus price
        vpus_ocpu_price = calculator.get_oci_price_ords('B91962')
        for block in okitjson['block_storage_volumes']:
            block_gb = float(block['size_in_gbs'])
            vpus_per_gb = float(block['vpus_per_gb'])
            PAYG, Monthly_Flex = calculator.Block_volume_GB_per_month(
                block_storage_price, block_gb, vpus_ocpu_price, vpus_per_gb)
            PAYG_Block_Volume_price += PAYG
            Monthly_Flex_Block_Volume_price += Monthly_Flex

            # parsing DBaaS storage to bom format
            bom.update_bom(df, 'B91961', block_gb, storage_per_month)
            bom.update_bom(df, 'B91962', block_gb *
                           vpus_per_gb, storage_per_month)

        print(PAYG_Block_Volume_price, Monthly_Flex_Block_Volume_price)
        # results.update({'block_storage_volumes': (PAYG_Block_Volume_price, Monthly_Flex_Block_Volume_price)})
        # no more monthly and annual flex is same price as PAYG
        results.update({'block_storage_volumes': (PAYG_Block_Volume_price, PAYG_Block_Volume_price)})

    else:
        results.update({'block_storage_volumes': (0, 0)})
    #############################################
    # Instance price calculator
    #############################################
    if okitjson['instances']:
        PAYG_Compute_OCPU = 0
        Monthly_Flex_Compute_OCPU = 0
        windows_os_ocpu = 0
        Windows_PAYG=0
        Windows_Monthly_Flex=0
        boot_volume_gb = 0
        total_boot_volume_gb = 0
        # Block volume price for PAYG and Monthly Flex are same vpus_per_gb for boot volume is 10 be default
        boot_volume_vpus_per_gb = 10

        for instance in okitjson['instances']:
            shape = instance['shape']
            OCPU, MEM, SSD, Compute_SKU = shapes.ComputeShape(shape)
            ocpu_price = calculator.get_oci_price_ords(Compute_SKU)
            PAYG, Monthly_Flex = calculator.OCPU_per_hr(ocpu_price, OCPU)
            PAYG_Compute_OCPU += PAYG
            Monthly_Flex_Compute_OCPU += Monthly_Flex

            #check if OS is windows
            instance_os = str(instance['source_details']['os']).lower()

            if instance_os == "windows":
                windows_price = calculator.get_oci_price_ords("B88318")
                Windows_PAYG, Windows_Monthly_Flex = calculator.OCPU_per_hr(windows_price, OCPU)
                windows_os_ocpu += OCPU
                # number of ocpu for windows os
                bom.update_bom(df, 'B88318', windows_os_ocpu, ocpu_per_month)
                #print(instance_os, windows_os_ocpu)


            # block storage price
            block_storage_price = calculator.get_oci_price_ords('B91961')
            # get vpus price
            vpus_ocpu_price = calculator.get_oci_price_ords('B91962')
            # Accumulate the size of boot volumes, this will be all balanced performence
            boot_volume_gb = float(instance['source_details']
                                    ['boot_volume_size_in_gbs'])
            total_boot_volume_gb += float(instance['source_details']
                                    ['boot_volume_size_in_gbs'])

            # parsing instance storage to bom format
            # total number of ocpu
            bom.update_bom(df, Compute_SKU, OCPU, ocpu_per_month)
            # boot colume
            bom.update_bom(df, 'B91961', boot_volume_gb, storage_per_month)
            bom.update_bom(df, 'B91962', boot_volume_gb *
                           boot_volume_vpus_per_gb, storage_per_month)

        PAYG_Boot_volume_price, Monthly_Flex_Boot_volume_price = calculator.Block_volume_GB_per_month(
            block_storage_price, total_boot_volume_gb, vpus_ocpu_price, boot_volume_vpus_per_gb)

        PAYG_Compute_price = round(
            PAYG_Compute_OCPU + PAYG_Boot_volume_price + Windows_PAYG, 2)
        Monthly_Flex_Compute_price = round(
            Monthly_Flex_Compute_OCPU + Monthly_Flex_Boot_volume_price + Windows_Monthly_Flex, 2)
        print(PAYG_Compute_price, Monthly_Flex_Compute_price)
        # results.update({'instances': (PAYG_Compute_price, Monthly_Flex_Compute_price)})
        # no more monthly and annual flex is same price as PAYG
        results.update({'instances': (PAYG_Compute_price, PAYG_Compute_price)})

    else:
        results.update({'instances': (0, 0)})
    #############################################
    # FastConnect price calculator
    #############################################
    if okitjson['fast_connects']:
        # Currentl OKIT does not have an option to select provisioned FC bandwidth
        bandwidth = "1Gbps"
        PAYG_FC_price = 0
        Monthly_Flex_FC_price = 0
        for fc in okitjson['fast_connects']:
            # bandwidth = fc['bandwidth']
            fc_SKU = shapes.FastConnect(bandwidth)
            # get fastconnect price
            fc_price = calculator.get_oci_price_ords(fc_SKU)
            PAYG, Monthly_Flex = calculator.OCPU_per_hr(fc_price, 1)
            PAYG_FC_price += PAYG
            Monthly_Flex_FC_price += Monthly_Flex

            # parsing DBaaS storage to bom format
            bom.update_bom(df, fc_SKU, 1, ocpu_per_month)

        print(PAYG_FC_price, Monthly_Flex_FC_price)
        # results.update({'fast_connects': (PAYG_FC_price, Monthly_Flex_FC_price)})
        # no more monthly and annual flex is same price as PAYG
        results.update({'fast_connects': (PAYG_FC_price, PAYG_FC_price)})

    else:
        results.update({'fast_connects': (0, 0)})
    #############################################
    # Load Balancer price calculator
    #############################################
    if okitjson['load_balancers']:
        PAYG_LB_price = 0
        Monthly_Flex_LB_price = 0
        for lb in okitjson['load_balancers']:
            shape_name = lb['shape']
            lb_SKU = shapes.LoadBalancer(shape_name)
            # get LB price
            lb_price = calculator.get_oci_price_ords(lb_SKU)
            PAYG, Monthly_Flex = calculator.OCPU_per_hr(lb_price, 1)
            PAYG_LB_price += PAYG
            Monthly_Flex_LB_price += Monthly_Flex

            # parsing DBaaS storage to bom format
            bom.update_bom(df, lb_SKU, 1, ocpu_per_month)

        print(PAYG_LB_price, Monthly_Flex_LB_price)
        # results.update({'load_balancers': (PAYG_LB_price, Monthly_Flex_LB_price)})
        # no more monthly and annual flex is same price as PAYG
        results.update({'load_balancers': (PAYG_LB_price, PAYG_LB_price)})

    else:
        results.update({'load_balancers': (0, 0)})
    #############################################
    # File Storage Service price calculator
    #############################################
    if okitjson['file_storage_systems']:
        # default 1TB
        fss_gb = 1000
        # get file storage service price
        fss_storage_price = calculator.get_oci_price_ords('B89057')
        PAYG_FSS_Storage_price, Monthly_Flex_FSS_Storage_price = calculator.Storage_GB_per_month(fss_storage_price,
                                                                                                 fss_gb)
        print(PAYG_FSS_Storage_price, Monthly_Flex_FSS_Storage_price)
        # results.update({'file_storage_systems': (PAYG_FSS_Storage_price, Monthly_Flex_FSS_Storage_price)})
        # no more monthly and annual flex is same price as PAYG
        results.update({'file_storage_systems': (PAYG_FSS_Storage_price, PAYG_FSS_Storage_price)})

        # parsing DBaaS storage to bom format
        bom.update_bom(df, 'B89057', fss_gb, storage_per_month)

    else:
        results.update({'file_storage_systems': (0, 0)})
    #############################################
    # Object Storage Service price calculator
    #############################################
    if okitjson['object_storage_buckets']:
        # default 1TB, 100K request,  fist 50K resuests will be free
        object_storage_gb = 1000
        requests = 1000000
        # get requests of object storage
        object_request_price = calculator.get_oci_price_ords('B91627')
        # fist 50K resuests will be free
        requests -= 50000
        PAYG_Request, Monthly_Flex_Request = calculator.Request_per_month(
            object_request_price, requests)

        # get object storage price
        object_storage_price = calculator.get_oci_price_ords('B91628')

        # first 10GB will be free
        object_storage_gb -= 10
        PAYG_Storage, Monthly_Flex_Storage = calculator.Storage_GB_per_month(
            object_storage_price, object_storage_gb)
        # PAYG
        PAYG_Object_Storage_price = round(PAYG_Storage + PAYG_Request, 2)
        # Monthly Flex
        Monthly_Flex_Object_Storage_price = round(
            Monthly_Flex_Storage + Monthly_Flex_Request, 2)
        print(PAYG_Object_Storage_price, Monthly_Flex_Object_Storage_price)
        # results.update({'object_storage_buckets': (PAYG_Object_Storage_price, Monthly_Flex_Object_Storage_price)})
        # no more monthly and annual flex is same price as PAYG
        results.update({'object_storage_buckets': (PAYG_Object_Storage_price, PAYG_Object_Storage_price)})

        # parsing DBaaS storage to bom format
        bom.update_bom(df, 'B91627', requests, storage_per_month)
        bom.update_bom(df, 'B91628', object_storage_gb, storage_per_month)

    else:
        results.update({'object_storage_buckets': (0, 0)})


    #############################################
    # Oracke Kubernetes Engine price calculator
    #############################################
    if okitjson['oke_clusters']:
        PAYG_Compute_OCPU = 0
        Monthly_Flex_Compute_OCPU = 0
        Windows_os_ocpu = 0
        Windows_PAYG = 0
        Windows_Monthly_Flex = 0
        boot_volume_gb = 0
        total_boot_volume_gb = 0
        # Block volume price for PAYG and Monthly Flex are same vpus_per_gb for boot volume is 10 be default
        boot_volume_vpus_per_gb = 10

        for oke in okitjson['oke_clusters']:
            for pool in oke['pools']:
                number_of_instance = int(pool['node_config_details']['size'])
                shape = pool['node_shape']
                boot_volume = int(pool['node_source_details'].get('boot_volume_size_in_gbs', 50))
                OCPU, MEM, SSD, Compute_SKU = shapes.ComputeShape(shape)
                ocpu_price = calculator.get_oci_price_ords(Compute_SKU)
                # total number of ocpu based on number of instance
                OCPU = OCPU * number_of_instance
                PAYG, Monthly_Flex = calculator.OCPU_per_hr(ocpu_price, OCPU)
                PAYG_Compute_OCPU += PAYG
                Monthly_Flex_Compute_OCPU += Monthly_Flex

                # total number of ocpu
                bom.update_bom(df, Compute_SKU, OCPU, ocpu_per_month)

                """
                # check if OS is windows, However, Kubernetes engine will run only linux at this moment.
                instance_os = str(pool['node_source_details']['os']).lower()


                # All Linux at this moment
                if instance_os == "windows":
                    windows_price = calculator.get_oci_price_ords("B88318")
                    Windows_PAYG, Windows_Monthly_Flex = calculator.OCPU_per_hr(windows_price, OCPU)
                    Windows_os_ocpu += OCPU
                    # number of ocpu for windows os
                    bom.update_bom(df, 'B88318', Windows_os_ocpu, ocpu_per_month)
                    # print(instance_os, windows_os_ocpu)
                """
                # block storage price
                block_storage_price = calculator.get_oci_price_ords('B91961')
                # get vpus price
                vpus_ocpu_price = calculator.get_oci_price_ords('B91962')
                # Accumulate the size of boot volumes, this will be all balanced performence
                boot_volume_gb = float(boot_volume * number_of_instance)
                total_boot_volume_gb += float(boot_volume * number_of_instance)

                # parsing instance storage to bom format

                # boot colume
                bom.update_bom(df, 'B91961', boot_volume_gb, storage_per_month)
                bom.update_bom(df, 'B91962', boot_volume_gb *
                               boot_volume_vpus_per_gb, storage_per_month)


        PAYG_Boot_volume_price, Monthly_Flex_Boot_volume_price = calculator.Block_volume_GB_per_month(
            block_storage_price, total_boot_volume_gb, vpus_ocpu_price, boot_volume_vpus_per_gb)

        PAYG_Compute_price = round(
            PAYG_Compute_OCPU + PAYG_Boot_volume_price + Windows_PAYG, 2)
        Monthly_Flex_Compute_price = round(
            Monthly_Flex_Compute_OCPU + Monthly_Flex_Boot_volume_price + Windows_Monthly_Flex, 2)
        print(PAYG_Compute_price, Monthly_Flex_Compute_price)


        results.update({'oke_clusters': (PAYG_Compute_price, PAYG_Compute_price)})

    else:
        results.update({'oke_clusters': (0, 0)})



    # call result app
    OKIT_RESULTS = parse_results_app(results, df)

    return OKIT_RESULTS

# update RESULTS, ARR table in OCIPRICE DB


def parse_results_app(results, df):
    RESULTS = []
    PAYG_Monthly = 0.0
    Monthly_Flex_Monthly = 0.0
    #filename = filename[:-5]
    filename = "okit_cost"
    CREATED_AT = str(datetime.datetime.now().strftime("%d-%b-%y"))
    xls_data = ''

    try:
        for resource, prices in results.items():
            row_data = {"FILENAME": filename, "RESOURCENAME": resource, "PAYG": prices[0], "ANNUAL_FLEX": prices[1],"CREATED_AT": CREATED_AT}
            # row_data = {"FILENAME": filename, "RESOURCENAME": resource, "PAYG": prices[0], "MONTHLY_FLEX": prices[1],"CREATED_AT": CREATED_AT}
            # row_data = (filename, resource, prices[0], prices[1])
            PAYG_Monthly += prices[0]
            Monthly_Flex_Monthly += prices[1]
            # Price per resource will be saved into RESULTS as PAYG and Monthly FLEX
            RESULTS.append(row_data)
        print("Price per resource:{}".format(RESULTS))

        # Get total PAYG/Monthle FLEX per Monthly/ARR
        Total_PAYG_Monthly = round(PAYG_Monthly, 2)
        #Total_Monthly_Flex_Monthly = round(Monthly_Flex_Monthly, 2)
        Total_PAYG_Yearly = round(Total_PAYG_Monthly * 12, 2)
        #Total_Monthly_Flex_Yearly = round(Total_Monthly_Flex_Monthly * 12, 2)
        # print("RESULTS - " + str(len(RESULTS)) + " Rows Inserted")

        # monthly, yearly PAYG, Monthle Flex
        #
        ARR_Result = {"FILENAME": filename, "PAYG": Total_PAYG_Monthly,"ANNUAL_FLEX": Total_PAYG_Monthly, "YEARLY_PAYG": Total_PAYG_Yearly,"YEARLY_ANNUAL_FLEX": Total_PAYG_Yearly, "CREATED_AT": CREATED_AT}
        print("Total price per monthly/yearly:{}".format(ARR_Result))

        OKIT_RESULTS = RESULTS.copy()
        # append a dictionary to a list
        ARR_Result_copy = ARR_Result.copy()
        # this will be a consolidated results that contains service price and total price
        OKIT_RESULTS.append(ARR_Result_copy)
        # print(type(OKIT_RESULTS), OKIT_RESULTS)

        xls_data = bom.finalize_bom(df).drop_duplicates()

    except Exception as e:
        print("\nError insering data into ARR - " + str(e) + "\n")
        raise SystemExit
    return OKIT_RESULTS, xls_data
