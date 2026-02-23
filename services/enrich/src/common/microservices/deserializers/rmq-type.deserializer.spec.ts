import { RMQTypeDeserializer } from './rmq-type.deserializer';

describe('RMQTypeDeserializer', () => {
  let deserializer: RMQTypeDeserializer;

  beforeEach(() => {
    deserializer = new RMQTypeDeserializer();
  });

  describe('deserialize', () => {
    it('should deserialize message with type in options', () => {
      const message = { artistId: 'test-uuid' };
      const options = { type: 'artist.enrich' };

      const result = deserializer.deserialize(message, options);

      expect(result).toEqual({
        pattern: 'artist.enrich',
        data: { artistId: 'test-uuid' },
      });
    });

    it('should set pattern to empty string when type is missing', () => {
      const message = { artistId: 'test-uuid' };

      const result = deserializer.deserialize(message);

      expect(result).toEqual({
        pattern: '',
        data: { artistId: 'test-uuid' },
      });
    });

    it('should set pattern to empty string when options is undefined', () => {
      const message = { artistId: 'test-uuid' };

      const result = deserializer.deserialize(message, undefined);

      expect(result).toEqual({
        pattern: '',
        data: { artistId: 'test-uuid' },
      });
    });

    it('should parse JSON string message', () => {
      const message = JSON.stringify({ artistId: 'test-uuid' });
      const options = { type: 'artist.enrich' };

      const result = deserializer.deserialize(message, options);

      expect(result).toEqual({
        pattern: 'artist.enrich',
        data: { artistId: 'test-uuid' },
      });
    });

    it('should handle complex message objects', () => {
      const message = {
        artistId: 'test-uuid',
        name: 'Test Artist',
        integrations: { discogs: 123 },
      };
      const options = { type: 'artist.enrich' };

      const result = deserializer.deserialize(message, options);

      expect(result).toEqual({
        pattern: 'artist.enrich',
        data: message,
      });
    });

    it('should use empty string pattern when type is empty string', () => {
      const message = { artistId: 'test-uuid' };
      const options = { type: '' };

      const result = deserializer.deserialize(message, options);

      expect(result).toEqual({
        pattern: '',
        data: { artistId: 'test-uuid' },
      });
    });
  });
});
