<?php
$file = '/var/www/html/app/etc/env.php';
$config = include $file;
$config['queue']['amqp'] = [
    'host' => 'rabbitmq', 'port' => '5672',
    'user' => getenv('RABBITMQ_USER'), 'password' => getenv('RABBITMQ_PASSWORD'), 'virtualhost' => '/'
];
$config['queue']['default_connection'] = 'amqp';
$config['cron_consumers_runner'] = ['cron_run' => true, 'max_messages' => 500, 'consumers' => []];
$config['queue']['consumers_wait_for_messages'] = 0;
$config['system']['default']['web']['unsecure']['base_url'] = getenv('BASE_URL');
$config['system']['default']['web']['secure']['base_url'] = getenv('BASE_URL');
file_put_contents($file, "<?php\nreturn " . var_export($config, true) . ";\n");
