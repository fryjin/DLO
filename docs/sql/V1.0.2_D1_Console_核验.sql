SELECT u.username, d.version, d.updated_at, LENGTH(d.data_json) AS json_length FROM account_documents AS d JOIN users AS u ON u.id=d.user_id ORDER BY u.username;
