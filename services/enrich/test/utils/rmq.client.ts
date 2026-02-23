import { connect, Channel, ChannelModel } from 'amqplib';
import { randomUUID } from 'crypto';

export default class RMQClient {
  private connection!: ChannelModel;
  private channel!: Channel;

  constructor(
    private readonly url: string,
    private readonly exchange: string,
    private readonly queue: string,
  ) {}

  async connect() {
    this.connection = await connect(this.url);
    this.channel = await this.connection.createChannel();

    await this.channel.assertExchange(this.exchange, 'topic', {
      durable: false,
      autoDelete: true,
    });

    await this.channel.assertQueue(this.queue, {
      autoDelete: true,
      durable: false,
    });

    await this.channel.bindQueue(this.queue, this.exchange, 'artist.#');
    return this.queue;
  }

  async close() {
    await this.channel.close();
    await this.connection.close();
  }

  publishMessage(message: unknown, routingKey: string) {
    const payload = Buffer.from(JSON.stringify(message));
    this.channel.publish(this.exchange, routingKey, payload, {
      type: routingKey,
      contentType: 'application/json',
      persistent: true,
      messageId: randomUUID(),
      correlationId: randomUUID(),
      timestamp: Date.now(),
    });
  }
}
