export class DiscogsError extends Error {
  constructor(
    message: string,
    public endpoint: string,
  ) {
    super(message);
    this.name = 'DiscogsError';
  }
}
