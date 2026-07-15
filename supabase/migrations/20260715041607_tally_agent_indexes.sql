-- Cover Tally agent foreign-key joins and installation cleanup paths.
CREATE INDEX tally_ledgers_installation_idx ON tally_ledgers(installation_id);
CREATE INDEX tally_pairing_installation_idx ON tally_pairing_codes(installation_id);
