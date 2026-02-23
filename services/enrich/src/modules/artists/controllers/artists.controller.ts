import { Controller } from '@nestjs/common';
import { ArtistCreateMessageDto } from '../dto/create-message.dto';
import ArtistsService from '../services/artists.service';
import { EventPattern, Payload } from '@nestjs/microservices';

@Controller()
export class ArtistsController {
  constructor(private service: ArtistsService) {}

  @EventPattern('artist.created')
  async handleCreated(@Payload() message: ArtistCreateMessageDto) {
    const artist = await this.service.getArtist(message.artistId);

    if (artist) {
      await this.service.enrich(artist);
    }
  }
}
