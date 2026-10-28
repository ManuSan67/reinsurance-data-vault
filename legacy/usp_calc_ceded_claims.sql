CREATE PROCEDURE dbo.usp_calc_ceded_claims
    @as_of_date DATE
AS
BEGIN
    SET NOCOUNT ON;

    IF OBJECT_ID('tempdb..#claims') IS NOT NULL DROP TABLE #claims;

    SELECT c.claim_number, c.treaty_number, c.loss_date, c.paid_to_date, c.outstanding, c.status, c.load_date
    INTO #claims
    FROM dbo.claims_bordereau c
    WHERE c.load_date = (SELECT MAX(c2.load_date)
                         FROM dbo.claims_bordereau c2
                         WHERE c2.claim_number = c.claim_number
                           AND c2.load_date <= @as_of_date);

    DELETE FROM dbo.ceded_claims WHERE as_of_date = @as_of_date;

    DECLARE @claim VARCHAR(30), @treaty VARCHAR(40), @gross DECIMAL(18,2),
            @type CHAR(2), @share DECIMAL(9,4), @ret DECIMAL(18,2), @lim DECIMAL(18,2),
            @ceded DECIMAL(18,2);

    DECLARE cur CURSOR FOR
        SELECT claim_number, treaty_number, paid_to_date + outstanding FROM #claims;

    OPEN cur;
    FETCH NEXT FROM cur INTO @claim, @treaty, @gross;

    WHILE @@FETCH_STATUS = 0
    BEGIN
        SELECT TOP 1 @type = treaty_type, @share = ceded_share, @ret = retention, @lim = limit_amount
        FROM dbo.treaties
        WHERE treaty_number = @treaty
        ORDER BY load_date DESC;

        IF @@ROWCOUNT > 0
        BEGIN
            IF @type = 'QS'
                SET @ceded = @gross * @share;
            ELSE IF @gross > @ret
                SET @ceded = CASE WHEN @gross - @ret > @lim THEN @lim ELSE @gross - @ret END;
            ELSE
                SET @ceded = 0;

            INSERT INTO dbo.ceded_claims (as_of_date, claim_number, treaty_number, gross_incurred, ceded_incurred)
            VALUES (@as_of_date, @claim, @treaty, @gross, ROUND(@ceded, 2));
        END

        FETCH NEXT FROM cur INTO @claim, @treaty, @gross;
    END

    CLOSE cur;
    DEALLOCATE cur;
END