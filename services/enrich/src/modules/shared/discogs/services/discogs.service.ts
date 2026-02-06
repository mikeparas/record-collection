import { HttpStatus, Injectable } from '@nestjs/common';
import { HttpService } from '@nestjs/axios';
import { lastValueFrom } from 'rxjs';
import {
  DiscogsArtist,
  DiscogsArtistResponseSchema,
  DiscogsImage,
} from '../schemas/artist.schema';
import { DiscogsError } from '../exceptions/exceptions';

@Injectable()
export class DiscogsService {
  constructor(private readonly http: HttpService) {}

  async enrichArtist(id: number): Promise<DiscogsArtist | null> {
    const resource = `https://api.discogs.com/artists/${id}`;
    const response = await lastValueFrom(this.http.get(resource));

    const status: HttpStatus = response.status;
    if (status === HttpStatus.NOT_FOUND) {
      return null;
    } else if (status !== HttpStatus.OK) {
      throw new DiscogsError(`Discogs API Error ${status}`, resource);
    }

    const data = DiscogsArtistResponseSchema.parse(response.data);

    return {
      id: data.id,
      name: data.name,
      url: data.uri,
      images: data.images
        .filter((img: DiscogsImage) => img.type === 'primary')
        .map((img: DiscogsImage) => img.uri),
    };
  }
}
