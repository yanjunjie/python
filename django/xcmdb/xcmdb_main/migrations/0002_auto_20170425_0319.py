# -*- coding: utf-8 -*-
# Generated by Django 1.10.6 on 2017-04-25 03:19
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('xcmdb_main', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='hostbaseinfo',
            name='machine_room',
            field=models.CharField(choices=[('IDC', 'idc'), ('WH', 'wh'), ('QF', 'qf')], max_length=5),
        ),
    ]
