-- stg_fia_trees.sql
-- Staging model: normalize FIA tree measurements.
-- Converts carbon from lbs to metric tons, filters to live trees.

with source as (
    select * from {{ source('raw', 'fia_tree') }}
),

cleaned as (
    select
        cn as tree_cn,
        plt_cn as plot_cn,
        condid as condition_id,
        subp as subplot,
        tree as tree_number,
        statecd as state_code,
        spcd as species_code,

        -- Measurements
        dia as diameter_inches,
        ht as height_ft,
        actualht as actual_height_ft,
        cr as crown_ratio_pct,
        statuscd as status_code,

        -- Carbon and biomass (raw in lbs, also convert to metric tons)
        carbon_ag as carbon_ag_lbs,
        carbon_bg as carbon_bg_lbs,
        drybio_ag as biomass_ag_lbs,
        drybio_bg as biomass_bg_lbs,
        (carbon_ag + coalesce(carbon_bg, 0)) as carbon_total_lbs,
        (carbon_ag + coalesce(carbon_bg, 0)) / 2204.62 as carbon_total_tonnes,

        -- Expansion factor (trees per acre this sample tree represents)
        tpa_unadj as trees_per_acre,

        -- Per-acre carbon (the metric that matters for comparison)
        carbon_ag * tpa_unadj as carbon_ag_per_acre_lbs,
        coalesce(carbon_bg, 0) * tpa_unadj as carbon_bg_per_acre_lbs,
        (carbon_ag + coalesce(carbon_bg, 0)) * tpa_unadj as carbon_total_per_acre_lbs,

        -- Volume
        volcfnet as volume_cuft_net,

        -- Status
        case statuscd
            when 1 then 'live'
            when 2 then 'dead'
            when 3 then 'removed'
            else 'unknown'
        end as tree_status,

        -- Is this loblolly pine? (Funga's primary species)
        (spcd = 131) as is_loblolly_pine,

        ingested_at

    from source
    where carbon_ag is not null
      and tpa_unadj is not null
      and tpa_unadj > 0
)

select * from cleaned
