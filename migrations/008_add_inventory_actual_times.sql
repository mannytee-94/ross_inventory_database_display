ALTER TABLE inventory
  ADD COLUMN ActualStartTime TIME NULL AFTER EstimatedStartTime,
  ADD COLUMN ActualEndTime TIME NULL AFTER ActualStartTime;
