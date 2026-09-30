# designed by mew
from django.db import migrations
from django.db.models import F


def remove_unused_photo_fields(apps, schema_editor):
    content = apps.get_model("cms", "ContentItem")
    items = content.objects.using(schema_editor.connection.alias).filter(kind="photo")
    obsolete = {"date", "album", "caption_zh", "caption_en"}
    for item in items.iterator():
        payload = {key: value for key, value in item.payload.items() if key not in obsolete}
        live = item.live
        if live:
            live = {
                **live,
                "data": {key: value for key, value in live["data"].items() if key not in obsolete},
            }
        if payload != item.payload or live != item.live:
            items.filter(pk=item.pk).update(payload=payload, live=live, version=F("version") + 1)


class Migration(migrations.Migration):
    dependencies = [("cms", "0001_initial")]
    operations = [migrations.RunPython(remove_unused_photo_fields, migrations.RunPython.noop)]
