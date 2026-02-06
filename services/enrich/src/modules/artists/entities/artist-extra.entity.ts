import { DiscogsArtist } from '../../shared/discogs/schemas/artist.schema';
import { Artist } from './artist.entity';
import {
  Column,
  CreateDateColumn,
  Entity,
  JoinColumn,
  OneToOne,
  PrimaryColumn,
  UpdateDateColumn,
} from 'typeorm';

export interface ArtistExtraData {
  discogs?: DiscogsArtist;
}

@Entity({ name: 'artist_extra' })
export class ArtistExtra {
  @PrimaryColumn({ type: 'uuid' })
  @OneToOne(() => Artist)
  @JoinColumn({
    name: 'id', // so a separate column isn't create
    referencedColumnName: 'id',
  })
  id: string;

  @CreateDateColumn({
    name: 'created_at',
  })
  createdAt: Date;

  @UpdateDateColumn({
    name: 'updated_at',
  })
  updatedAt: Date;

  @Column('jsonb')
  data: ArtistExtraData | null;

  constructor(id: string, data: ArtistExtraData | null) {
    this.id = id;
    this.data = data;
  }
}
