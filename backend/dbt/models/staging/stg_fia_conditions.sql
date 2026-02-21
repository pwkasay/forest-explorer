-- stg_fia_conditions.sql
-- Staging model: normalize FIA condition (stand) data.

with source as (
    select * from {{ source('raw', 'fia_cond') }}
),

cleaned as (
    select
        cn as condition_cn,
        plt_cn as plot_cn,
        condid as condition_id,
        statecd as state_code,
        fortypcd as forest_type_code,
        stdage as stand_age_years,
        stdszcd as stand_size_class,
        siteclcd as site_productivity_class,
        slope as slope_pct,
        aspect as aspect_degrees,
        owncd as ownership_code,
        owngrpcd as ownership_group_code,
        condprop_unadj as condition_proportion,

        -- Ownership categories (important for land partner models)
        case owngrpcd
            when 10 then 'National Forest'
            when 20 then 'Other Federal'
            when 30 then 'State/Local'
            when 40 then 'Private'
            else 'Unknown'
        end as ownership_category,

        -- Stand maturity
        case
            when stdage < 20 then 'young'
            when stdage between 20 and 60 then 'mid-rotation'
            when stdage between 61 and 100 then 'mature'
            when stdage > 100 then 'old-growth'
            else 'unknown'
        end as maturity_class,

        -- Site productivity (1=best, 7=worst)
        case
            when siteclcd between 1 and 2 then 'high'
            when siteclcd between 3 and 4 then 'medium'
            when siteclcd between 5 and 7 then 'low'
            else 'unknown'
        end as site_productivity,

        ingested_at

    from source
)

select * from cleaned
