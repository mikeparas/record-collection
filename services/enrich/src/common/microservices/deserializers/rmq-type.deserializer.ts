import { Deserializer, ReadPacket } from '@nestjs/microservices';

export interface RMQTypeDeserializerOptions {
  type: string;
}

/**
 * Custom RMQ deserializer that converts non-NestJS messages into ReadPackets
 * using the type from options as the pattern.
 *
 * Transforms: { "artistId": "uuid" }
 * Into: { "pattern": "event.type", "data": { "artistId": "uuid" } }
 */
export class RMQTypeDeserializer implements Deserializer {
  deserialize(
    message: string | Record<string, unknown>,
    options?: RMQTypeDeserializerOptions,
  ): ReadPacket {
    // If message is a string, parse it
    const data: unknown =
      typeof message === 'string' ? JSON.parse(message) : message;

    const pattern = options?.type || '';

    return {
      pattern,
      data,
    };
  }
}
