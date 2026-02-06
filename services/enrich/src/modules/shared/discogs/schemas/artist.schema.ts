import z from 'zod';

export interface DiscogsArtist {
  id: number;
  name: string;
  url: string;
  images: string[] | null;
}

const DiscogsImageSchema = z.looseObject({
  type: z.literal(['primary', 'secondary']),
  uri: z.string(),
});

export type DiscogsImage = z.infer<typeof DiscogsImageSchema>;

export const DiscogsArtistResponseSchema = z.looseObject({
  name: z.string(),
  id: z.int(),
  uri: z.string(),
  images: z.array(DiscogsImageSchema),
});

export type DiscogsArtistResponse = z.infer<typeof DiscogsArtistResponseSchema>;
