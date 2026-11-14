<?php
declare(strict_types=1);
namespace Local\ErpConnector\Observer;

use Magento\Framework\Event\Observer;
use Magento\Framework\Event\ObserverInterface;
use Magento\Framework\HTTP\Client\CurlFactory;
use Psr\Log\LoggerInterface;

/** Small synchronous development connector; ERP failure never reverses a Magento save. */
class Sync implements ObserverInterface
{
    public function __construct(private CurlFactory $curlFactory, private LoggerInterface $logger) {}

    public function execute(Observer $observer): void
    {
        try {
            $event = $observer->getEvent();
            $model = $event->getProduct() ?: ($event->getOrder() ?: $event->getCustomer());
            if (!$model || !$model->getId()) {
                return;
            }
            $payload = ['external_id' => (string)$model->getId(), 'source' => 'magento'];
            if ($event->getProduct()) {
                $kind = 'products';
                $payload += ['sku' => $model->getSku(), 'name' => $model->getName(),
                    'price' => (float)$model->getPrice(), 'status' => $model->getStatus()];
            } elseif ($event->getOrder()) {
                $kind = 'orders';
                $items = [];
                foreach ($model->getAllVisibleItems() as $item) {
                    $items[] = ['sku' => $item->getSku(), 'name' => $item->getName(),
                        'qty' => (float)$item->getQtyOrdered(), 'price' => (float)$item->getPrice()];
                }
                $payload += ['increment_id' => $model->getIncrementId(), 'status' => $model->getStatus(),
                    'total' => (float)$model->getGrandTotal(), 'currency' => $model->getOrderCurrencyCode(),
                    'customer_email' => $model->getCustomerEmail(), 'items' => $items];
            } else {
                $kind = 'customers';
                $payload += ['email' => $model->getEmail(), 'firstname' => $model->getFirstname(),
                    'lastname' => $model->getLastname()];
            }
            $client = $this->curlFactory->create();
            $client->setTimeout(3);
            $client->addHeader('Content-Type', 'application/json');
            $client->addHeader('Authorization', 'Bearer ' . getenv('ERP_API_TOKEN'));
            $client->post(rtrim(getenv('ERP_BASE_URL') ?: 'http://erp:8080', '/') . '/api/' . $kind,
                json_encode($payload, JSON_THROW_ON_ERROR));
            if ($client->getStatus() >= 400) {
                $this->logger->warning('Local ERP rejected request', [
                    'entity' => $kind, 'id' => $model->getId(), 'http_status' => $client->getStatus()
                ]);
            }
        } catch (\Throwable $error) {
            $this->logger->error('Local ERP sync failed: ' . $error->getMessage());
        }
    }
}
