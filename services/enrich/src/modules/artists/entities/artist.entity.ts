import { Column, Entity, PrimaryColumn } from 'typeorm';

export interface Integrations {
  discogs?: number;
}

@Entity({
  name: 'artists',
  synchronize: false,
})
export class Artist {
  @PrimaryColumn({
    type: 'uuid',
    nullable: false,
  })
  id!: string;

  @Column({
    type: 'varchar',
    nullable: false,
  })
  name!: string;

  @Column({
    name: 'sort_name',
    type: 'varchar',
    nullable: false,
  })
  sortName!: string;

  @Column({
    type: 'jsonb',
    default: {},
  })
  integrations!: Integrations;

  constructor(partial: Partial<Artist>) {
    Object.assign(this, partial);
  }
}
