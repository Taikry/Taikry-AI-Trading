# មគ្គុទ្ទេសក៍ Backup និង Migration

## Database migrations

កម្មវិធីចាប់ផ្តើមដោយអាន migration តាមលំដាប់លេខ និងកត់ត្រាកំណែដែលបានអនុវត្តក្នុងតារាង `schema_migrations`។ Migration មួយត្រូវបានកត់ត្រាបន្ទាប់ពីវាបញ្ចប់ដោយជោគជ័យ។ ពេលបន្ថែម schema ថ្មី សូមបន្ថែម migration ថ្មីដែលមានលេខកំណែបន្ទាប់ក្នុង `taikry/database/versioned_migrations.py`។ រក្សា migration ឱ្យអាចដំណើរការឡើងវិញដោយសុវត្ថិភាព ព្រោះការដាក់ពង្រាយអាចត្រូវបានចាប់ផ្តើមឡើងវិញ។

## បង្កើត backup ដោយដៃ

```powershell
python scripts/backup_database.py --output-dir backups --retention-days 14
```

- SQLite ត្រូវបានចម្លងដោយ SQLite backup API ហើយពិនិត្យ integrity មុនពេលដាក់ឈ្មោះជាឯកសារ backup ពេញលេញ។
- PostgreSQL ត្រូវការ `pg_dump` នៅក្នុង PATH ហើយបង្កើតឯកសារ custom-format។ Password ត្រូវបានផ្ញើតាម environment របស់ process មិនដាក់ក្នុង command line ទេ។
- ការសម្អាតឯកសារចាស់ធ្វើតែក្នុងថត `--output-dir` និងលើឯកសារដែលមាន prefix `taikry_backup_` ប៉ុណ្ណោះ។ កំណត់ `--retention-days 0` ដើម្បីមិនលុប backup ចាស់។

## ការដាក់ប្រើនៅ production

1. កំណត់ `DATABASE_BACKUP_DIR` ទៅថតដែលមាន persistent storage និងកំណត់ `DATABASE_BACKUP_RETENTION_DAYS` តាមគោលការណ៍រក្សាទុករបស់អ្នក។
2. កំណត់ scheduler ឱ្យរត់ backup រៀងរាល់ថ្ងៃ ហើយចម្លង backup ចេញពីម៉ាស៊ីនកម្មវិធីទៅ storage ផ្សេងទៀត។
3. ដំឡើង PostgreSQL client tools នៅលើម៉ាស៊ីន backup ប្រសិនបើប្រើ PostgreSQL។
4. ធ្វើ restore drill ជាប្រចាំលើ database សាកល្បង មុនពេលពឹងផ្អែកលើ backup ក្នុងហេតុការណ៍ពិត។
5. កំណត់ `REDIS_URL` ទៅ Redis ដែលមានសុវត្ថិភាព។ ប្រព័ន្ធ login ប្រើ Redis ដើម្បីចែករំលែក failed-login rate limit រវាង worker; ប្រសិនបើ Redis មិនអាចប្រើបាន វាត្រឡប់ទៅ rate limit ក្នុង worker នីមួយៗ។

Backup មិនត្រូវបានដំណើរការដោយស្វ័យប្រវត្តិនៅពេល server ចាប់ផ្តើមទេ។ ត្រូវកំណត់ scheduler នៅ host ឬ CI/CD ដែលទទួលខុសត្រូវចំពោះ backup។
