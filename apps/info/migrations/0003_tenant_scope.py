from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("info", "0002_trainingarticle_is_compulsory_trainingarticle_status_and_more"), ("organization", "0001_initial")]
    operations = [
        migrations.AddField(model_name="category", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="info_categories", to="organization.organization")),
        migrations.AddField(model_name="tag", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="info_tags", to="organization.organization")),
        migrations.AddField(model_name="faq", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="faqs", to="organization.organization")),
        migrations.AddField(model_name="sop", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sops", to="organization.organization")),
        migrations.AddField(model_name="policyexplanation", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="policy_explanations", to="organization.organization")),
        migrations.AddField(model_name="trainingarticle", name="organization", field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="training_articles", to="organization.organization")),
        migrations.AlterField(model_name="category", name="name", field=models.CharField(max_length=255)),
        migrations.AlterField(model_name="category", name="slug", field=models.SlugField(blank=True, max_length=255)),
        migrations.AlterField(model_name="tag", name="name", field=models.CharField(max_length=100)),
        migrations.AlterField(model_name="tag", name="slug", field=models.SlugField(blank=True, max_length=100)),
        migrations.AddConstraint(model_name="category", constraint=models.UniqueConstraint(fields=("organization", "name"), name="unique_info_category_name_per_org")),
        migrations.AddConstraint(model_name="category", constraint=models.UniqueConstraint(fields=("organization", "slug"), name="unique_info_category_slug_per_org")),
        migrations.AddConstraint(model_name="tag", constraint=models.UniqueConstraint(fields=("organization", "name"), name="unique_info_tag_name_per_org")),
        migrations.AddConstraint(model_name="tag", constraint=models.UniqueConstraint(fields=("organization", "slug"), name="unique_info_tag_slug_per_org")),
    ]
