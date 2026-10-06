ALTER TABLE inventory
  CHANGE COLUMN HoursWorkedPlanned EstimatedDuration DECIMAL(8,2) NULL,
  ADD COLUMN EstimatedStartTime TIME NULL AFTER ControllerName;
